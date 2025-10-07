"""Email utilities for MHE Backend.

Apply Rules: Implement email templates with proper HTML and plain text versions.
Apply Rules: Use Django signals for automated email notifications.
Apply Rules: Test email delivery in staging environments.
"""
from typing import List, Dict, Any, Optional
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging
from django.template.defaultfilters import slugify
from django.utils import timezone

logger = logging.getLogger(__name__)

# --- STATIC ASSETS ---
MHE_WEBSITE_URL = "https://www.mhebazar.in"
MHE_LOGO_URL = "https://www.mhebazar.in/mhe-logo.png"
# ---------------------


def get_product_url(product) -> str:
    """Generate the full, user-facing URL for the product."""
    product_slug = slugify(product.name)
    # URL format: https://www.mhebazar.in/product/[product-name-in-slug]-[id]
    return f"{MHE_WEBSITE_URL}/product/{product_slug}-{product.id}"


class EmailService:
    """Centralized email service for consistent email handling."""
    
    @staticmethod
    def send_template_email(
        template_name: str,
        context: Dict[str, Any],
        subject: str,
        to_emails: List[str],
        from_email: Optional[str] = None
    ) -> bool:
        """
        Send email using HTML template with automatic plain text fallback.
        """
        try:
            from_email = from_email or settings.DEFAULT_FROM_EMAIL
            
            # Render HTML template
            html_content = render_to_string(f'email/{template_name}.html', context)
            
            # Create plain text version by stripping HTML tags
            text_content = strip_tags(html_content)
            
            # Create email message
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=to_emails
            )
            msg.attach_alternative(html_content, "text/html")
            
            result = msg.send()
            
            if result:
                logger.info(f"Email sent successfully: {subject} to {to_emails}")
            else:
                logger.error(f"Failed to send email: {subject} to {to_emails}")
                
            return bool(result)
            
        except Exception as e:
            # Logging the specific template error is crucial for debugging
            logger.error(f"Email sending error (Template: {template_name}.html): {e}") 
            return False
    
    @staticmethod
    def _build_enquiry_context(instance, enquiry_type: str) -> Dict[str, Any]:
        """Builds context with safe access and professional details."""
        
        # 1. Get Vendor Info safely from product owner
        vendor_info = {
            'company_name': 'N/A',
            'email': 'N/A',
            'phone': 'N/A'
        }
        try:
            vendor_object = instance.product.user.vendor.first()
            if vendor_object:
                vendor_info['company_name'] = vendor_object.company_name
                vendor_info['email'] = vendor_object.company_email
                vendor_info['phone'] = vendor_object.company_phone
        except AttributeError:
            pass 

        # 2. Build common context
        context = {
            f'{enquiry_type}': instance,
            'product_url': get_product_url(instance.product),
            'website_url': MHE_WEBSITE_URL, # New: Global website URL
            'logo_url': MHE_LOGO_URL, # New: Logo URL
            'current_date': timezone.now().strftime("%d %b, %Y"), # Fallback date
            
            # --- SAFE VARIABLES for templates ---
            'customer_name': instance.full_name, 
            'customer_email': instance.email,
            
            # Vendor Details
            'vendor_company_name': vendor_info['company_name'],
            'vendor_email': vendor_info['email'],
            
            # All fields for detailed display tables (using underscores)
            'full_details': {
                'Customer_Name': instance.full_name,
                'Email': instance.email,
                'Phone': instance.phone,
                'Product': instance.product.name,
                'Vendor_Company': vendor_info['company_name'],
                'Submitted_On': instance.created_at.strftime("%d %b, %Y %I:%M %p"),
                'Status': instance.status.capitalize(),
            }
        }
        
        # 3. Add type-specific details
        if enquiry_type == 'quote':
            # FIXED: Using underscore key for consistency
            context['full_details']['Company_Name'] = instance.company_name or 'N/A'
            context['full_details']['Message'] = instance.message
        elif enquiry_type == 'rental':
            context['full_details']['Address'] = instance.address or 'N/A'
            context['full_details']['Start_Date'] = instance.start_date.strftime("%d %b, %Y")
            context['full_details']['End_Date'] = instance.end_date.strftime("%d %b, %Y")
            context['full_details']['Notes'] = instance.notes or 'N/A'

        return context

    # --- QUOTE EMAILS (Methods remain the same) ---
    @staticmethod
    def send_quote_confirmation(quote) -> bool:
        """Send quote confirmation email to customer (uses quote.email)."""
        try:
            context = EmailService._build_enquiry_context(quote, 'quote')
            subject = f"Confirmation: Your Quote Request for {quote.product.name}"
            recipient_email = quote.email 
            
            if not recipient_email:
                logger.warning(f"Skipping quote confirmation: No email found for quote ID {quote.id}")
                return False

            return EmailService.send_template_email(
                template_name='quote_customer_confirmation',
                context=context,
                subject=subject,
                to_emails=[recipient_email]
            )
        except Exception as e:
            logger.error(f"Failed to send quote confirmation: {str(e)}")
            return False
            
    @staticmethod
    def send_quote_to_vendor(quote) -> bool:
        """Send quote notification email to the product's vendor."""
        try:
            context = EmailService._build_enquiry_context(quote, 'quote')
            vendor_email = context['vendor_email']
            
            if vendor_email == 'N/A':
                 logger.warning(f"Skipping vendor quote notification: Vendor email not found for product {quote.product.id}")
                 return False

            subject = f"Action Required: New Quote Request for {quote.product.name}"
            
            return EmailService.send_template_email(
                template_name='quote_vendor_notification',
                context=context,
                subject=subject,
                to_emails=[vendor_email]
            )
        except Exception as e:
            logger.error(f"Failed to send quote to vendor: {str(e)}")
            return False
    
    @staticmethod
    def send_quote_admin_notification(quote) -> bool:
        """Send quote notification email to admin."""
        try:
            context = EmailService._build_enquiry_context(quote, 'quote')
            subject = f"ALERT: New Quote Request - {quote.product.name}"
            
            return EmailService.send_template_email(
                template_name='quote_admin_notification',
                context=context,
                subject=subject,
                to_emails=[settings.ADMIN_EMAIL]
            )
        except Exception as e:
            logger.error(f"Failed to send quote admin notification: {str(e)}")
            return False

    @staticmethod
    def send_quote_status_update(quote, status_change: str) -> bool:
        """Send email when a quote status is approved/rejected."""
        try:
            context = EmailService._build_enquiry_context(quote, 'quote')
            context['status_change'] = status_change.capitalize()
            
            subject = f"Update: Your Quote Request for {quote.product.name} is {status_change.capitalize()}"
            recipient_email = quote.email 
            
            return EmailService.send_template_email(
                template_name=f'quote_status_{status_change}',
                context=context,
                subject=subject,
                to_emails=[recipient_email]
            )
        except Exception as e:
            logger.error(f"Failed to send quote status update ({status_change}): {str(e)}")
            return False
    
    # --- RENTAL EMAILS ---
    @staticmethod
    def send_rental_confirmation(rental) -> bool:
        """Send rental confirmation email to customer (uses rental.email)."""
        try:
            context = EmailService._build_enquiry_context(rental, 'rental')
            subject = f"Confirmation: Your Rental Request for {rental.product.name}"
            recipient_email = rental.email
            
            if not recipient_email:
                logger.warning(f"Skipping rental confirmation: No email found for rental ID {rental.id}")
                return False

            return EmailService.send_template_email(
                template_name='rental_customer_confirmation',
                context=context,
                subject=subject,
                to_emails=[recipient_email]
            )
        except Exception as e:
            logger.error(f"Failed to send rental confirmation: {str(e)}")
            return False

    @staticmethod
    def send_rental_to_vendor(rental) -> bool:
        """Send rental notification email to the product's vendor."""
        try:
            context = EmailService._build_enquiry_context(rental, 'rental')
            vendor_email = context['vendor_email']
            
            if vendor_email == 'N/A':
                 logger.warning(f"Skipping vendor rental notification: Vendor email not found for product {rental.product.id}")
                 return False

            subject = f"Action Required: New Rental Request for {rental.product.name}"
            
            return EmailService.send_template_email(
                template_name='rental_vendor_notification',
                context=context,
                subject=subject,
                to_emails=[vendor_email]
            )
        except Exception as e:
            logger.error(f"Failed to send rental to vendor: {str(e)}")
            return False
    
    @staticmethod
    def send_rental_admin_notification(rental) -> bool:
        """Send rental notification email to admin."""
        try:
            context = EmailService._build_enquiry_context(rental, 'rental')
            subject = f"ALERT: New Rental Request - {rental.product.name}"
            
            return EmailService.send_template_email(
                template_name='rental_admin_notification',
                context=context,
                subject=subject,
                to_emails=[settings.ADMIN_EMAIL]
            )
        except Exception as e:
            logger.error(f"Failed to send rental admin notification: {str(e)}")
            return False
            
    @staticmethod
    def send_rental_status_update(rental, status_change: str) -> bool:
        """Send email when a rental status is approved/rejected/returned."""
        try:
            context = EmailService._build_enquiry_context(rental, 'rental')
            context['status_change'] = status_change.capitalize()
            
            subject = f"Update: Your Rental Request for {rental.product.name} is {status_change.capitalize()}"
            recipient_email = rental.email 
            
            return EmailService.send_template_email(
                template_name=f'rental_status_{status_change}',
                context=context,
                subject=subject,
                to_emails=[recipient_email]
            )
        except Exception as e:
            logger.error(f"Failed to send rental status update ({status_change}): {str(e)}")
            return False
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
        """Builds context with safe access and professional details, including special handling for Quote Address."""
        
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

        # 2. Check if this is a Generic Vendor Lead
        is_generic = False
        if enquiry_type == 'quote':
            is_generic = '[GENERIC VENDOR LEAD]' in (instance.message or '')
        elif enquiry_type == 'rental':
            is_generic = '[GENERIC VENDOR LEAD]' in (instance.notes or '')
        
        display_product_name = "Offline General Enquiry" if is_generic else instance.product.name

        # 3. Initialize default context with placeholders
        context = {
            f'{enquiry_type}': instance,
            'product_url': get_product_url(instance.product),
            'website_url': MHE_WEBSITE_URL,
            'logo_url': MHE_LOGO_URL,
            'current_date': timezone.now().strftime("%Y"),
            
            # --- SAFE VARIABLES for templates ---
            'customer_name': instance.full_name, 
            'product_name': display_product_name,
            'is_generic': is_generic,
            
            # Vendor Details
            'vendor_company_name': vendor_info['company_name'],
            'vendor_email': vendor_info['email'],
            
            # All fields for detailed display tables (using underscores)
            'full_details': {
                'Customer_Name': instance.full_name,
                'Email': instance.email,
                'Phone': instance.phone,
                'Product': display_product_name,
                'Vendor_Company': vendor_info['company_name'],
                'Submitted_On': instance.created_at.strftime("%d %b, %Y %I:%M %p"),
                'Status': instance.status.capitalize(),
                'Company_Name': 'N/A',
                'Company_Address': 'N/A',
                'Message': 'N/A',
                'Notes': 'N/A',
            }
        }
        
        # 3. Add type-specific details
        if enquiry_type == 'quote':
            context['full_details']['Company_Name'] = instance.company_name or 'N/A'
            raw_message = instance.message or ''
            
            # --- ADDRESS EXTRACTION LOGIC ---
            company_address = 'N/A'
            cleaned_message = raw_message
            
            address_key = "Company Address:"
            if address_key in raw_message:
                try:
                    # Find the start of "Company Address:"
                    start_index = raw_message.find(address_key)
                    
                    # Extract everything after the key, strip leading/trailing whitespace
                    address_part = raw_message[start_index + len(address_key):].strip()
                    company_address = address_part.split('\n')[0].strip() # Take the first line as address
                    
                    # Remove the Company Address line from the remaining message
                    cleaned_message = raw_message[:start_index].rstrip() + raw_message[start_index + len(address_key) + len(address_part):].lstrip()
                    cleaned_message = cleaned_message.strip()
                    
                except Exception as e:
                    logger.warning(f"Failed to parse company address from quote ID {instance.id}: {e}")
                    # If parsing fails, use the raw message but address is N/A
                    company_address = 'N/A (See Message)'

            context['full_details']['Company_Address'] = company_address or 'N/A'
            
            # Strip the generic lead marker for the email body
            if is_generic:
                cleaned_message = cleaned_message.replace('[GENERIC VENDOR LEAD]', '').strip()
                
            context['full_details']['Message'] = cleaned_message or 'N/A'

            
        elif enquiry_type == 'rental':
            
            raw_notes = instance.notes or ''
            
            # --- NOTES CLEANING AND EXTRACTION LOGIC (NEW) ---
            company_name_from_notes = 'N/A'
            is_whatsapp_contact = False
            cleaned_notes = raw_notes
            
            # 1. Check for WhatsApp status
            if 'whatsapp:' in raw_notes.lower():
                is_whatsapp_contact = True
                cleaned_notes = cleaned_notes.replace('WhatsApp:', '').replace('whatsapp:', '').strip()
                
            # 2. Extract Company Name and clean the notes further
            company_key = "Company Name:"
            if company_key in raw_notes:
                try:
                    # Find the start of the Company Name value
                    start_index = raw_notes.lower().find(company_key.lower())
                    
                    # Extract everything after the key
                    name_part = raw_notes[start_index + len(company_key):].strip()
                    
                    # Company Name is typically the first line after the key
                    company_name_from_notes = name_part.split('\n')[0].strip()
                    
                    # Remove the Company Name line from the notes
                    # This regex replacement handles both start-of-string and mid-string placement.
                    import re
                    cleaned_notes = re.sub(r'Company Name:\s*.+?(?:\n|$)', '', cleaned_notes, flags=re.IGNORECASE).strip()
                    
                except Exception as e:
                    logger.warning(f"Failed to parse company name from rental ID {instance.id}: {e}")
                    
            # Final cleanup of extra newlines/spaces
            cleaned_notes = cleaned_notes.strip()
            if is_generic:
                cleaned_notes = cleaned_notes.replace('[GENERIC VENDOR LEAD]', '').strip()
            # --- END NOTES CLEANING AND EXTRACTION LOGIC ---
            
            
            context['full_details']['Address'] = instance.address or 'N/A'
            context['full_details']['Start_Date'] = instance.start_date.strftime("%d %b, %Y")
            context['full_details']['End_Date'] = instance.end_date.strftime("%d %b, %Y")
            
            # Use extracted/cleaned fields in context
            context['full_details']['Notes'] = cleaned_notes or 'No additional notes provided.'
            context['full_details']['Company_Name'] = company_name_from_notes
            context['full_details']['is_whatsapp_contact'] = is_whatsapp_contact # NEW FLAG
            
            # For consistent display, rename Address to Company_Address for table use
            context['full_details']['Company_Address'] = instance.address or 'N/A'
            
        return context

    # --- QUOTE EMAILS (Methods remain the same) ---
    @staticmethod
    def send_quote_confirmation(quote) -> bool:
        """Send quote confirmation email to customer (uses quote.email)."""
        try:
            context = EmailService._build_enquiry_context(quote, 'quote')
            subject = f"Confirmation: Your Quote Request for {context['product_name']}"
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

            subject = f"Action Required: New Quote Request for {context['product_name']}"
            
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
        """Send quote notification email to MHE administrators."""
        try:
            context = EmailService._build_enquiry_context(quote, 'quote')
            subject = f"New Quote Request: {context['product_name']}"
            
            admin_emails = [settings.ADMIN_EMAIL] if isinstance(settings.ADMIN_EMAIL, str) else settings.ADMIN_EMAIL
            
            return EmailService.send_template_email(
                template_name='quote_admin_notification',
                context=context,
                subject=subject,
                to_emails=admin_emails
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
            subject = f"Confirmation: Your Rental Request for {context['product_name']}"
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

            subject = f"Action Required: New Rental Request for {context['product_name']}"
            
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
        """Send rental notification email to MHE administrators."""
        try:
            context = EmailService._build_enquiry_context(rental, 'rental')
            subject = f"New Rental Request: {context['product_name']}"
            
            admin_emails = [settings.ADMIN_EMAIL] if isinstance(settings.ADMIN_EMAIL, str) else settings.ADMIN_EMAIL
            
            return EmailService.send_template_email(
                template_name='rental_admin_notification',
                context=context,
                subject=subject,
                to_emails=admin_emails
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
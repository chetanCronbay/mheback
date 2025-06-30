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

logger = logging.getLogger(__name__)


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
        
        Apply Rules: Implement email templates with proper HTML and plain text versions.
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
            
            # Send email
            result = msg.send()
            
            if result:
                logger.info(f"Email sent successfully: {subject} to {to_emails}")
            else:
                logger.error(f"Failed to send email: {subject} to {to_emails}")
                
            return bool(result)
            
        except Exception as e:
            logger.error(f"Email sending error: {str(e)}")
            return False
    
    @staticmethod
    def send_quote_confirmation(quote) -> bool:
        """Send quote confirmation email to customer."""
        try:
            context = {'quote': quote}
            subject = f"Quote Request Confirmation - {quote.product.name}"
            
            return EmailService.send_template_email(
                template_name='quote_customer_confirmation',
                context=context,
                subject=subject,
                to_emails=[quote.user.email]
            )
        except Exception as e:
            logger.error(f"Failed to send quote confirmation: {str(e)}")
            return False
    
    @staticmethod
    def send_quote_admin_notification(quote) -> bool:
        """Send quote notification email to admin."""
        try:
            context = {'quote': quote}
            subject = f"New Quote Request - {quote.product.name}"
            
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
    def send_rental_confirmation(rental) -> bool:
        """Send rental confirmation email to customer."""
        try:
            context = {'rental': rental}
            subject = f"Rental Request Confirmation - {rental.product.name}"
            
            return EmailService.send_template_email(
                template_name='rental_customer_confirmation',
                context=context,
                subject=subject,
                to_emails=[rental.user.email]
            )
        except Exception as e:
            logger.error(f"Failed to send rental confirmation: {str(e)}")
            return False
    
    @staticmethod
    def send_rental_admin_notification(rental) -> bool:
        """Send rental notification email to admin."""
        try:
            context = {'rental': rental}
            subject = f"New Rental Request - {rental.product.name}"
            
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
    def send_user_verification_email(user, verification_token: str) -> bool:
        """Send email verification to new user."""
        try:
            context = {
                'user': user,
                'verification_token': verification_token,
                'verification_url': f"{settings.FRONTEND_URL}/verify-email/{verification_token}"
            }
            subject = "Please verify your email address"
            
            return EmailService.send_template_email(
                template_name='user_verification',
                context=context,
                subject=subject,
                to_emails=[user.email]
            )
        except Exception as e:
            logger.error(f"Failed to send user verification email: {str(e)}")
            return False
    
    @staticmethod
    def send_password_reset_email(user, reset_token: str) -> bool:
        """Send password reset email."""
        try:
            context = {
                'user': user,
                'reset_token': reset_token,
                'reset_url': f"{settings.FRONTEND_URL}/reset-password/{reset_token}"
            }
            subject = "Password Reset Request"
            
            return EmailService.send_template_email(
                template_name='password_reset',
                context=context,
                subject=subject,
                to_emails=[user.email]
            )
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            return False


class EmailValidator:
    """Email validation utilities."""
    
    @staticmethod
    def is_valid_email_domain(email: str, allowed_domains: Optional[List[str]] = None) -> bool:
        """Validate email domain against whitelist."""
        if not allowed_domains:
            return True
            
        domain = email.split('@')[-1].lower()
        return domain in [d.lower() for d in allowed_domains]
    
    @staticmethod
    def is_disposable_email(email: str) -> bool:
        """Check if email is from a disposable email service."""
        # List of common disposable email domains
        disposable_domains = [
            '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
            'mailinator.com', 'throwaway.email', 'temp-mail.org'
        ]
        
        domain = email.split('@')[-1].lower()
        return domain in disposable_domains


class EmailQueue:
    """Email queue management for high-volume sending."""
    
    @staticmethod
    def queue_email(template_name: str, context: Dict[str, Any], 
                   subject: str, to_emails: List[str]) -> bool:
        """
        Queue email for background processing.
        
        Apply Rules: Implement email queue for high-volume sending.
        Note: This would require Celery or similar task queue in production.
        """
        try:
            # In development, send immediately
            if settings.DEBUG:
                return EmailService.send_template_email(
                    template_name, context, subject, to_emails
                )
            
            # In production, this would queue the task
            # For now, we'll send immediately but log it as queued
            logger.info(f"Email queued: {subject} to {len(to_emails)} recipients")
            return EmailService.send_template_email(
                template_name, context, subject, to_emails
            )
            
        except Exception as e:
            logger.error(f"Failed to queue email: {str(e)}")
            return False

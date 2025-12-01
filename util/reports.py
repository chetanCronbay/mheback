from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q

from products.models import Product, Quote, Rental
from users.models import User, Vendor, Role

# --- STATIC ASSETS ---
MHE_WEBSITE_URL = "https://api.mhebazar.in"
MHE_LOGO_URL = "https://www.mhebazar.in/mhe-logo.png"

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role.id == Role.ADMIN)

def _get_date_ranges():
    today = timezone.now().date()
    # Last Week: Previous Monday to Sunday
    start_of_week = today - timedelta(days=today.weekday())
    last_week_start = start_of_week - timedelta(weeks=1)
    last_week_end = start_of_week - timedelta(days=1)
    
    # Last Month: 1st to last day of previous month
    first = today.replace(day=1)
    last_month_end = first - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    return {
        'today': today,
        'last_week_start': last_week_start,
        'last_week_end': last_week_end,
        'last_month_start': last_month_start,
        'last_month_end': last_month_end
    }

def _get_product_stats(products_queryset, date_ranges):
    """
    Calculate detailed product stats for a given queryset of products.
    Returns a dictionary with total counts and categorized counts.
    """
    # Filter for approved products only
    approved_products = products_queryset.filter(status='approved')
    
    # Last Month Approved
    last_month_approved = approved_products.filter(
        created_at__date__gte=date_ranges['last_month_start'],
        created_at__date__lte=date_ranges['last_month_end']
    )

    def count_by_type(queryset):
        return {
            'new': queryset.filter(type__contains='new').count(),
            'used': queryset.filter(type__contains='used').count(),
            'rental': queryset.filter(type__contains='rental').count(),
            'attachments': queryset.filter(type__contains='attachments').count(),
        }

    return {
        'total_approved': approved_products.count(),
        'last_month_approved_count': last_month_approved.count(),
        'total_by_type': count_by_type(approved_products),
        'last_month_by_type': count_by_type(last_month_approved),
    }

def _get_vendor_stats(user, date_ranges):
    """Calculate stats for a specific vendor user."""
    # Get all products for this vendor
    products = Product.objects.filter(user=user)
    
    # Base queries
    quotes = Quote.objects.filter(product__in=products)
    rentals = Rental.objects.filter(product__in=products)
    
    # Product Stats
    product_stats = _get_product_stats(products, date_ranges)

    stats = {
        'total_quotes': quotes.count(),
        'total_rentals': rentals.count(),
        
        'quotes_last_month': quotes.filter(
            created_at__date__gte=date_ranges['last_month_start'],
            created_at__date__lte=date_ranges['last_month_end']
        ).count(),
        
        'rentals_last_month': rentals.filter(
            created_at__date__gte=date_ranges['last_month_start'],
            created_at__date__lte=date_ranges['last_month_end']
        ).count(),
        
        'quotes_last_week': quotes.filter(
            created_at__date__gte=date_ranges['last_week_start'],
            created_at__date__lte=date_ranges['last_week_end']
        ).count(),
        
        'rentals_last_week': rentals.filter(
            created_at__date__gte=date_ranges['last_week_start'],
            created_at__date__lte=date_ranges['last_week_end']
        ).count(),
        
        # Merge product stats
        **product_stats
    }
    return stats

def _get_dashboard_context():
    date_ranges = _get_date_ranges()
    
    # 1. Overall Stats
    total_quotes = Quote.objects.count()
    total_rentals = Rental.objects.count()
    
    quotes_last_month = Quote.objects.filter(
        created_at__date__gte=date_ranges['last_month_start'],
        created_at__date__lte=date_ranges['last_month_end']
    ).count()
    
    rentals_last_month = Rental.objects.filter(
        created_at__date__gte=date_ranges['last_month_start'],
        created_at__date__lte=date_ranges['last_month_end']
    ).count()
    
    quotes_last_week = Quote.objects.filter(
        created_at__date__gte=date_ranges['last_week_start'],
        created_at__date__lte=date_ranges['last_week_end']
    ).count()
    
    rentals_last_week = Rental.objects.filter(
        created_at__date__gte=date_ranges['last_week_start'],
        created_at__date__lte=date_ranges['last_week_end']
    ).count()
    
    # Overall Product Stats
    all_products = Product.objects.all()
    overall_product_stats = _get_product_stats(all_products, date_ranges)

    overall_stats = {
        'total_quotes': total_quotes,
        'total_rentals': total_rentals,
        'quotes_last_month': quotes_last_month,
        'rentals_last_month': rentals_last_month,
        'quotes_last_week': quotes_last_week,
        'rentals_last_week': rentals_last_week,
        **overall_product_stats
    }

    # 2. Vendor List
    # Get users who have a Vendor profile AND are active AND have the Vendor role
    vendors = Vendor.objects.select_related('user').filter(
        user__role__id=Role.VENDOR,
        user__is_active=True
    ).all()
    
    vendor_list = []
    for vendor in vendors:
        user = vendor.user
        stats = _get_vendor_stats(user, date_ranges)
        
        # Get logo from user profile
        logo_url = MHE_LOGO_URL
        if user.profile_photo:
            logo_url = user.profile_photo.url
            
        vendor_data = {
            'id': vendor.id,
            'user_id': user.id,
            'company_name': vendor.company_name,
            'name': user.get_full_name(),
            'email': vendor.company_email, # Use company email for reports
            'phone': vendor.company_phone,
            'logo_url': logo_url,
            'stats': stats
        }
        vendor_list.append(vendor_data)
        
    return {
        'overall_stats': overall_stats,
        'vendors': vendor_list,
        'date_ranges': date_ranges,
        'MHE_LOGO_URL': MHE_LOGO_URL
    }

@user_passes_test(is_admin)
def vendor_report_dashboard(request):
    context = _get_dashboard_context()
    return render(request, 'reports/vendor_report_dashboard.html', context)

# --- PREVIEW VIEWS ---

@user_passes_test(is_admin)
def preview_admin_report(request, report_type):
    """Preview the admin report before sending."""
    context = _get_dashboard_context()
    date_ranges = context['date_ranges']
    
    if report_type == 'weekly':
        period_name = "Last Week"
        start_date = date_ranges['last_week_start']
        end_date = date_ranges['last_week_end']
    else:
        period_name = "Last Month"
        start_date = date_ranges['last_month_start']
        end_date = date_ranges['last_month_end']

    email_context = {
        'overall_stats': context['overall_stats'],
        'vendors': context['vendors'],
        'period_name': period_name,
        'start_date': start_date,
        'end_date': end_date,
        'MHE_LOGO_URL': MHE_LOGO_URL,
        'report_type': report_type
    }
    
    # Render the email HTML
    email_html = render_to_string('reports/admin_report_email.html', email_context)
    
    return render(request, 'reports/report_preview.html', {
        'email_html': email_html,
        'action_url': f"/reports/send-admin/{report_type}/",
        'title': f"Preview Admin {report_type.title()} Report",
        'recipient_list': ['ulhas.makeshwar@greentechmh.com', 'manik.thapar@greentechmh.com', 'sumedh.ramteke@mhebazar.com', 'rakesh.a@greentechmh.com', 'marketing.1@mhebazar.com','developer@cronbaytechnologies.com']
    })

@user_passes_test(is_admin)
def preview_vendor_report(request, vendor_id):
    """Preview a single vendor report."""
    vendor = get_object_or_404(Vendor, id=vendor_id)
    user = vendor.user
    date_ranges = _get_date_ranges()
    stats = _get_vendor_stats(user, date_ranges)
    
    logo_url = MHE_LOGO_URL
    if user.profile_photo:
         if user.profile_photo.url.startswith('http'):
            logo_url = user.profile_photo.url
         else:
            logo_url = f"{MHE_WEBSITE_URL}{user.profile_photo.url}"

    email_context = {
        'vendor_name': vendor.company_name,
        'contact_name': user.get_full_name(),
        'stats': stats,
        'period_name': date_ranges['last_month_start'].strftime('%B %Y'),
        'start_date': date_ranges['last_month_start'],
        'end_date': date_ranges['last_month_end'],
        'MHE_LOGO_URL': MHE_LOGO_URL,
        'VENDOR_LOGO_URL': logo_url,
        'plan_name': "Plan-Gold (OEM)"
    }
    
    email_html = render_to_string('reports/vendor_monthly_report_email.html', email_context)
    
    return render(request, 'reports/report_preview.html', {
        'email_html': email_html,
        'action_url': f"/reports/send-vendor/{vendor.id}/",
        'title': f"Preview Report for {vendor.company_name}",
        'recipient_list': [vendor.company_email, 'sumedh.ramteke@mhebazar.com', 'rakesh.a@greentechmh.com', 'marketing.1@mhebazar.com','developer@cronbaytechnologies.com']
    })

@user_passes_test(is_admin)
def preview_all_vendor_reports(request):
    """Preview all vendor reports in a list."""
    # Filter: Role=Vendor (2) AND Active=True
    vendors = Vendor.objects.select_related('user').filter(
        user__role__id=Role.VENDOR,
        user__is_active=True
    ).all()
    
    date_ranges = _get_date_ranges()
    
    previews = []
    all_recipients = []
    
    for vendor in vendors:
        user = vendor.user
        stats = _get_vendor_stats(user, date_ranges)
        
        logo_url = MHE_LOGO_URL
        if user.profile_photo:
             if user.profile_photo.url.startswith('http'):
                logo_url = user.profile_photo.url
             else:
                logo_url = f"{MHE_WEBSITE_URL}{user.profile_photo.url}"

        email_context = {
            'vendor_name': vendor.company_name,
            'contact_name': user.get_full_name(),
            'stats': stats,
            'period_name': date_ranges['last_month_start'].strftime('%B %Y'),
            'start_date': date_ranges['last_month_start'],
            'end_date': date_ranges['last_month_end'],
            'MHE_LOGO_URL': MHE_LOGO_URL,
            'VENDOR_LOGO_URL': logo_url,
            'plan_name': "Plan-Gold (OEM)"
        }
        
        email_html = render_to_string('reports/vendor_monthly_report_email.html', email_context)
        previews.append({
            'vendor_name': vendor.company_name,
            'html': email_html
        })
        all_recipients.append(vendor.company_email)

    # Add CCs to the recipient list display (just once to show they are included)
    all_recipients.extend(['(CC) sumedh.ramteke@mhebazar.com', '(CC) rakesh.a@greentechmh.com', '(CC) marketing.1@mhebazar.com','(cc) developer@cronbaytechnologies.com'])

    return render(request, 'reports/report_preview_bulk.html', {
        'previews': previews,
        'action_url': "/reports/send-all-vendors/",
        'title': "Preview All Vendor Monthly Reports",
        'recipient_list': all_recipients
    })


# --- SENDING VIEWS (Modified to handle POST) ---

def _send_email(subject, template_name, context, to_emails, cc_emails=None, reply_to=None):
    html_content = render_to_string(template_name, context)
    text_content = "Please view this email in an HTML compatible viewer."
    
    msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, to_emails, cc=cc_emails, reply_to=reply_to)
    msg.attach_alternative(html_content, "text/html")
    msg.send()

@user_passes_test(is_admin)
def send_admin_report(request, report_type):
    if request.method != 'POST':
        return redirect('vendor-report-dashboard')

    context = _get_dashboard_context()
    date_ranges = context['date_ranges']
    
    if report_type == 'weekly':
        subject = f"MHE Bazar Weekly Admin Report ({date_ranges['last_week_start']} - {date_ranges['last_week_end']})"
        period_name = "Last Week"
        start_date = date_ranges['last_week_start']
        end_date = date_ranges['last_week_end']
    else:
        subject = f"MHE Bazar Monthly Admin Report ({date_ranges['last_month_start'].strftime('%B %Y')})"
        period_name = "Last Month"
        start_date = date_ranges['last_month_start']
        end_date = date_ranges['last_month_end']

    email_context = {
        'overall_stats': context['overall_stats'],
        'vendors': context['vendors'],
        'period_name': period_name,
        'start_date': start_date,
        'end_date': end_date,
        'MHE_LOGO_URL': MHE_LOGO_URL,
        'report_type': report_type
    }
    
    to_emails = ['ulhas.makeshwar@greentechmh.com']
    cc_emails = [
        'manik.thapar@greentechmh.com',
        'sumedh.ramteke@mhebazar.com',
        'rakesh.a@greentechmh.com',
        'marketing.1@mhebazar.com',
        'developer@cronbaytechnologies.com'
    ]
    
    try:
        _send_email(subject, 'reports/admin_report_email.html', email_context, to_emails, cc_emails)
        messages.success(request, f"Admin {report_type} report sent successfully.")
    except Exception as e:
        messages.error(request, f"Failed to send admin report: {str(e)}")
        
    return redirect('vendor-report-dashboard')

@user_passes_test(is_admin)
def send_vendor_report(request, vendor_id):
    if request.method != 'POST':
        return redirect('vendor-report-dashboard')

    try:
        vendor = Vendor.objects.select_related('user').get(id=vendor_id)
        _send_single_vendor_report(vendor)
        messages.success(request, f"Report sent to {vendor.company_name}.")
        
    except Vendor.DoesNotExist:
        messages.error(request, "Vendor not found.")
    except Exception as e:
        messages.error(request, f"Failed to send report to vendor {vendor_id}: {str(e)}")
        
    return redirect('vendor-report-dashboard')

@user_passes_test(is_admin)
def send_all_vendor_reports(request):
    if request.method != 'POST':
        return redirect('vendor-report-dashboard')

    # Filter: Role=Vendor (2) AND Active=True
    vendors = Vendor.objects.select_related('user').filter(
        user__role__id=Role.VENDOR,
        user__is_active=True
    ).all()
    
    success_count = 0
    fail_count = 0
    
    for vendor in vendors:
        try:
            _send_single_vendor_report(vendor)
            success_count += 1
        except Exception as e:
            fail_count += 1
            print(f"Failed to send to {vendor.company_name}: {e}")
            
    messages.success(request, f"Bulk send complete. Success: {success_count}, Failed: {fail_count}")
    return redirect('vendor-report-dashboard')

def _send_single_vendor_report(vendor):
    user = vendor.user
    date_ranges = _get_date_ranges()
    stats = _get_vendor_stats(user, date_ranges)
    
    subject = f"Your Monthly Performance Report - {date_ranges['last_month_start'].strftime('%B %Y')} - MHE Bazar"
    
    logo_url = MHE_LOGO_URL
    if user.profile_photo:
         if user.profile_photo.url.startswith('http'):
            logo_url = user.profile_photo.url
         else:
            logo_url = f"{MHE_WEBSITE_URL}{user.profile_photo.url}"

    email_context = {
        'vendor_name': vendor.company_name,
        'contact_name': user.get_full_name(),
        'stats': stats,
        'period_name': date_ranges['last_month_start'].strftime('%B %Y'),
        'start_date': date_ranges['last_month_start'],
        'end_date': date_ranges['last_month_end'],
        'MHE_LOGO_URL': MHE_LOGO_URL,
        'VENDOR_LOGO_URL': logo_url,
        'plan_name': "Plan-Gold (OEM)"
    }
    
    to_emails = [vendor.company_email]
    cc_emails = [
        'sumedh.ramteke@mhebazar.com',
        'rakesh.a@greentechmh.com',
        'marketing.1@mhebazar.com',
        'developer@cronbaytechnologies.com'
    ]
    
    _send_email(subject, 'reports/vendor_monthly_report_email.html', email_context, to_emails, cc_emails)
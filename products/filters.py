import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta, date

#  Quote, Rental models are imported from products.models
from products.models import Quote, Rental 

# Helper to get the start of the week (Monday)
def get_monday(d):
    return d - timedelta(days=d.weekday())

# --- Custom Date Filters ---
class CustomDateRangeFilter(django_filters.DateFilter):
    """Filters objects created between two dates (inclusive) using a single URL parameter."""
    def filter(self, qs, value):
        if value:
            try:
                # Expecting value format: "YYYY-MM-DD,YYYY-MM-DD"
                start_date_str, end_date_str = value.split(',')
                start_date = date.fromisoformat(start_date_str)
                end_date = date.fromisoformat(end_date_str) + timedelta(days=1) # Extend to include the entire end_date
                
                return qs.filter(created_at__gte=start_date, created_at__lt=end_date)
            except ValueError:
                return qs # Return original queryset if format is invalid
        return qs

class CustomPeriodFilter(django_filters.CharFilter):
    """Filters objects based on a relative or explicit time period."""
    def filter(self, qs, value):
        if not value:
            return qs

        now = timezone.now()
        start_date = None
        end_date = now + timedelta(days=1) # Default to 'tomorrow' to include today

        value = value.lower()

        if value == 'this_week':
            start_date = get_monday(now.date())
        elif value == 'last_week':
            last_monday = get_monday(now.date()) - timedelta(weeks=1)
            start_date = last_monday
            end_date = get_monday(now.date())
        elif value == 'this_month':
            start_date = now.date().replace(day=1)
        elif value == 'last_month':
            first_of_this_month = now.date().replace(day=1)
            last_month_end = first_of_this_month
            start_date = (last_month_end - timedelta(days=1)).replace(day=1)
            end_date = first_of_this_month
        elif len(value) == 7 and '-' in value:
            # Handles 'YYYY-MM' format 
            try:
                year, month = map(int, value.split('-'))
                start_date = date(year, month, 1)
                # Calculate the first day of the *next* month
                if month == 12:
                    end_date = date(year + 1, 1, 1)
                else:
                    end_date = date(year, month + 1, 1)
            except ValueError:
                return qs # Invalid format

        if start_date:
            return qs.filter(created_at__gte=start_date, created_at__lt=end_date)
            
        return qs

# --- FilterSet Definition ---
class BaseRequestFilterSet(django_filters.FilterSet):
    # -------------------------------------------------------------
    # 💡 ADVANCED DATE FILTERS
    # -------------------------------------------------------------
    date_range = CustomDateRangeFilter(field_name='created_at')
    period = CustomPeriodFilter(field_name='created_at')
    
    # -------------------------------------------------------------
    # 💡 VENDOR FILTERS (New Flexible Filters)
    # -------------------------------------------------------------
    vendor_id = django_filters.NumberFilter(
        field_name='product__user__id', 
        label="Filter by Vendor User ID (product__user__id)"
    )
    vendor_user_id = django_filters.NumberFilter(
        field_name='product__user__id', 
        label="Filter by Vendor User ID (alias)"
    )
    vendor_brand = django_filters.CharFilter(
        field_name='product__user__vendor__brand', 
        lookup_expr='icontains',
        label="Filter by Vendor Brand (contains)"
    )
    vendor_company_name = django_filters.CharFilter(
        field_name='product__user__vendor__company_name', 
        lookup_expr='icontains',
        label="Filter by Vendor Company Name (contains)"
    )
    vendor_email = django_filters.CharFilter(
        field_name='product__user__vendor__company_email', 
        lookup_expr='iexact',
        label="Filter by Vendor Company Email (exact)"
    )
    
    # -------------------------------------------------------------
    # CUSTOMER FILTER (Kept for completeness, formerly user_id)
    # -------------------------------------------------------------
    customer_id = django_filters.NumberFilter(
        field_name='user__id', 
        label="Filter by Customer Requestor ID (user__id)"
    ) 

    class Meta:
        fields = ['status']

class QuoteFilterSet(BaseRequestFilterSet):
    class Meta(BaseRequestFilterSet.Meta):
        model = Quote

class RentalFilterSet(BaseRequestFilterSet):
    class Meta(BaseRequestFilterSet.Meta):
        model = Rental
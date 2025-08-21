from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

class WriteOnlyAnonRateThrottle(AnonRateThrottle):
    scope = "anon"  # explicitly set
    def allow_request(self, request, view):
      if request.method in ('GET', 'HEAD', 'OPTIONS'):
          return True
      ip_address = self.get_ident(request)
      print(f"Throttling check for IP: {ip_address}, scope={self.scope}, rate={self.get_rate()}")
      return super().allow_request(request, view)

class WriteOnlyUserRateThrottle(UserRateThrottle):
    scope = "user"  # explicitly set
    def allow_request(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return super().allow_request(request, view)

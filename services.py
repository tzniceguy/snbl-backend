class PesaPalService:
    """Service class for handling PesaPal API interactions"""
    base_url = 'https://cybqa.pesapal.com/pesapalv3/'

    def __init__(self):
        self.credentials = PesaPalCredentials.objects.first()
        if not self.credentials:
            raise ValueError("PesaPal credentials not configured")

        self.base_url = self.credentials.base_url

    def get_auth_token(self):
        """Get or create PesaPal authentication token"""
        current_token = PesaPalToken.objects.filter(is_active=True).first()

        if current_token and current_token.is_valid():
            return current_token.token

        url = f"{self.base_url}/api/Auth/RequestToken"
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        payload = {
            'consumer_key': self.credentials.consumer_key,
            'consumer_secret': self.credentials.consumer_secret
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()
        token = data['token']
        expires_in = data['expiryDate']

        # Deactivate old tokens
        PesaPalToken.objects.filter(is_active=True).update(is_active=False)

        # Create new token
        PesaPalToken.objects.create(
            token=token,
            expires_at=expires_in,
            is_active=True
        )

        return token

    def register_ipn_url(self, url):
        """Register IPN URL with PesaPal"""
        token = self.get_auth_token()

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }

        payload = {
            'url': url,
            'ipn_notification_type': 'GET'
        }

        response = requests.post(
            f"{self.base_url}/api/URLSetup/RegisterIPN",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def submit_order(self, order, callback_url):
        """Submit order to PesaPal for payment"""
        token = self.get_auth_token()

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }

        # Create PesaPal transaction record
        transaction = PesaPalTransaction.objects.create(
            order=order,
            merchant_reference=f"ORDER-{order.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            amount=order.amount,
            currency='KES'  # Update as needed
        )

        payload = {
            'id': transaction.merchant_reference,
            'currency': transaction.currency,
            'amount': float(transaction.amount),
            'description': f'Payment for Order #{order.id}',
            'callback_url': callback_url,
            'notification_id': settings.PESAPAL_IPN_ID,
            'billing_address': {
                'email_address': order.customer.email,
                'phone_number': order.customer.phone,
                'country_code': 'KE',  # Update as needed
                'first_name': order.customer.first_name,
                'last_name': order.customer.last_name,
            }
        }

        response = requests.post(
            f"{self.base_url}/api/Transactions/SubmitOrderRequest",
            headers=headers,
            json=payload
        )
        response.raise_for_status()

        data = response.json()
        transaction.pesapal_tracking_id = data.get('order_tracking_id')
        transaction.save()

        return data

    def check_payment_status(self, order_tracking_id):
        """Check payment status from PesaPal"""
        token = self.get_auth_token()

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }

        response = requests.get(
            f"{self.base_url}/api/Transactions/GetTransactionStatus?orderTrackingId={order_tracking_id}",
            headers=headers
        )
        response.raise_for_status()

        return response.json()

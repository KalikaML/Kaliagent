import email
from email.message import EmailMessage
from datetime import datetime
from procurement.models import Product, ProcurementRequest, Supplier, Quote
from django.test import TestCase

# Helper to create a sample email

def create_sample_email(subject, body, from_addr, date_str=None):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = 'test@kalika.com'
    if date_str:
        msg['Date'] = date_str
    msg.set_content(body)
    return msg

class TestQuoteComparison(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name="Widget A")
        self.rfq_sent_time = datetime(2025, 12, 1, 10, 0, 0)
        self.request = ProcurementRequest.objects.create(
            title="Widget A RFQ",
            product=self.product,
            quantity="10",
            status="rfqs-sent",
            rfq_sent_time=self.rfq_sent_time
        )

    def test_multiple_quotes_comparison(self):
        # Simulate receiving multiple quotes after RFQ sent
        quotes_data = [
            {"supplier": "supplier1@example.com", "price": 1000, "lead_time": 7, "payment_terms": "100% Advance", "discount": 5},
            {"supplier": "supplier2@example.com", "price": 950, "lead_time": 10, "payment_terms": "50% Advance", "discount": 0},
            {"supplier": "supplier3@example.com", "price": 1100, "lead_time": 5, "payment_terms": "100% on delivery", "discount": 10},
        ]
        for idx, q in enumerate(quotes_data, start=1):
            supplier, _ = Supplier.objects.get_or_create(
                procurement_request=self.request,
                name=q["supplier"],
                email=q["supplier"]
            )
            Quote.objects.create(
                procurement_request=self.request,
                supplier=supplier,
                price=q["price"],
                quantity="10",
                lead_time_days=q["lead_time"],
                payment_terms=q["payment_terms"],
                discount=q["discount"],
                parsed_from_email_uid=f"test-uid-{idx}"
            )
        # Retrieve and compare quotes
        quotes = Quote.objects.filter(procurement_request=self.request)
        best_quote = min(quotes, key=lambda q: q.price)
        print("All quotes:")
        for q in quotes:
            print(f"Supplier: {q.supplier.name}, Price: {q.price}, Lead Time: {q.lead_time_days}, Payment: {q.payment_terms}, Discount: {q.discount}")
        print(f"\nBest quote is from {best_quote.supplier.name} at price {best_quote.price}")
        # Assert best quote is as expected
        self.assertEqual(best_quote.supplier.email, "supplier2@example.com")
        self.assertEqual(best_quote.price, 950)

# Example usage:
if __name__ == "__main__":
    # Create a sample email
    subject = "Quotation for Widget A"
    body = "Dear Team,\nPlease find attached the quotation for Widget A.\nTotal: 10000 INR\nGST: 1800 INR\nGrand Total: 11800 INR\nProduct: Widget A\nQuantity: 10\nUnit Price: 1000 INR\nLead Time: 7 days\nPayment Terms: 100% Advance\nDiscount: 5%\n"
    from_addr = "supplier@example.com"
    date_str = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
    sample_email = create_sample_email(subject, body, from_addr, date_str)

    # Print the raw email for inspection
    print(sample_email.as_string())

    # Optionally, test parsing logic (if you have a function to parse EmailMessage directly)
    # result = parse_quote_email(sample_email)
    # print(result)

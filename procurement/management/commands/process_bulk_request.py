# procurement/management/commands/process_bulk_request.py

import time
from django.core.management.base import BaseCommand
from django.core.management import call_command
from procurement.models import ProcurementRequest
from procurement.utils import send_rfqs_for_request

class Command(BaseCommand):
    help = 'Runs the full end-to-end process for a request: scrape suppliers and then send RFQs.'

    def add_arguments(self, parser):
        parser.add_argument('request_id', type=int, help='The ID of the procurement request to process.')

    def handle(self, *args, **options):
        request_id = options['request_id']
        try:
            request = ProcurementRequest.objects.get(pk=request_id)
            self.stdout.write(self.style.SUCCESS(f"🚀 Starting end-to-end processing for request ID {request_id}: '{request.title}'"))

            # --- Step 1: Scrape for suppliers ---
            self.stdout.write(f"[{time.ctime()}] Running supplier scraping agent...")
            
            # EXPLANATION: It calls the existing scrape_suppliers command to find vendors.
            # The request status will be changed to 'awaiting-approval' by this command.
            call_command('scrape_suppliers', str(request_id))
            
            # Refresh request object from DB to get the latest state after scraping is done
            request.refresh_from_db()
            
            if request.status != 'awaiting-approval':
                self.stdout.write(self.style.WARNING(f"Supplier scraping did not result in 'awaiting-approval' status. Current status: '{request.status}'. Aborting RFQ send."))
                return

            self.stdout.write(self.style.SUCCESS(f"✅ Supplier scraping complete. Found {request.suppliers.count()} potential suppliers."))

            # --- Step 2: Automatically send RFQs ---
            self.stdout.write(f"[{time.ctime()}] Automatically sending RFQs...")
            
            # EXPLANATION: After scraping, it immediately calls the function to send RFQ emails.
            # There is no manual approval step in this automated flow.
            success, message = send_rfqs_for_request(request_id)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f"✅ RFQs sent successfully. {message}"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Failed to send RFQs. Reason: {message}"))

            self.stdout.write(self.style.SUCCESS(f"🏁 End-to-end processing finished for request ID {request_id}."))

        except ProcurementRequest.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Procurement request with ID {request_id} does not exist."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An unexpected error occurred: {e}"))
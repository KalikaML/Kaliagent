# procurement/management/commands/run_quote_scanner.py

import time
from django.core.management.base import BaseCommand
from procurement.utils import process_incoming_quotes

class Command(BaseCommand):
    help = 'Runs a continuous background agent to scan emails for all quotes.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting independent quote scanning agent...'))

        while True:
            try:
                self.stdout.write(f'[{time.ctime()}] Running independent quote scan...')
                new_quotes = process_incoming_quotes()
                if new_quotes > 0:
                    self.stdout.write(self.style.SUCCESS(f'✅ Found and processed {new_quotes} new quote(s).'))
                else:
                    self.stdout.write('No new processable quotes found.')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'An error occurred in the agent loop: {e}'))
            
            self.stdout.write('Scan complete. Waiting for 300 seconds...')
            time.sleep(300) # हर 5 मिनट में जांचें
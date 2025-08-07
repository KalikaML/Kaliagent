import textwrap
from django.core.management.base import BaseCommand
from ai_agent_pitch.models import EmailTemplate

class Command(BaseCommand):
    """
    A Django management command to seed the database with initial email templates.
    This command is idempotent, meaning it can be run multiple times without
    creating duplicate templates.
    """
    help = 'Seeds the database with initial email templates for the AI Pitch Agent.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Seeding Initial Email Templates ---'))

        # --- Template 1: Dark Theme ---
        template1_html = textwrap.dedent("""
            <center style="width: 100%; background-color: #0D1117;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0" bgcolor="#0D1117">
                    <tbody><tr>
                        <td align="center" style="padding: 20px;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: auto;">
                                <tbody><tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <h1 style="font-family: Arial, sans-serif; font-size: 28px; font-weight: bold; color: #ffffff; margin: 0; letter-spacing: 1px;">Kalika AI</h1>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" bgcolor="#161B22" style="border-radius: 24px; padding: 40px 20px;">
                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <tbody><tr>
                                                <td align="center" style="padding-bottom: 10px;">
                                                    <h2 style="font-family: Arial, sans-serif; font-size: 40px; font-weight: bold; margin: 0; color: #ffffff;">
                                                        Collaborate with <span style="color: #4facfe;">Kalika AI</span>
                                                    </h2>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td align="center" style="padding: 10px 0 30px 0;">
                                                    <p style="font-family: Arial, sans-serif; font-size: 18px; color: #a1a9c0; margin: 0; max-width: 450px; line-height: 1.5;">
                                                        Dear [Recipient],<br>
                                                        As a valued partner, discover AI tools designed to streamline your operations and support your business growth.
                                                    </p>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td align="center" style="padding-bottom: 40px;">
                                                    <a href="https://www.kalisoftai.in/?campaign_id=[CAMPAIGN_ID]" target="_blank" style="font-size: 16px; font-weight: bold; font-family: sans-serif; color: #ffffff; text-decoration: none; border-radius: 30px; padding: 16px 32px; background-color: #8b5cf6; display: inline-block;">Learn About Our AI Solutions</a>
                                                </td>
                                            </tr>
                                        </tbody></table>
                                    </td>
                                </tr>
                                <tr><td style="height: 20px;"></td></tr>
                                <tr>
                                    <td bgcolor="#161B22" style="border-radius: 24px; padding: 30px 20px;">
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #f0f2f5; margin: 0 0 5px 0;">B2B E-commerce Ads AI</h3>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #a1a9c0; margin: 0; line-height: 1.5;">
                                                            Create targeted ad campaigns to enhance your B2B e-commerce strategies and connect with potential partners.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #f0f2f5; margin: 0 0 5px 0;">YouTube Shorts AI</h3>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #a1a9c0; margin: 0; line-height: 1.5;">
                                                            Automatically identify engaging moments in long videos to create compelling short-form content for social media.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 30px 20px;">
                                        <p style="font-family: Arial, sans-serif; font-size: 14px; color: #718096; margin: 0 0 15px 0;">
                                            © 2025 Kalika AI. All rights reserved.<br>
                                            Sent by Kalika AI, contact@kalisoftai.in
                                        </p>
                                        <p style="font-family: Arial, sans-serif; font-size: 12px; color: #718096; margin: 0;">
                                            To unsubscribe, reply with "Unsubscribe".
                                        </p>
                                    </td>
                                </tr>
                            </tbody></table>
                        </td>
                    </tr>
                </tbody></table>
            </center>
        """).strip()

        # --- Template 2: Light Theme ---
        template2_html = textwrap.dedent("""
            <center style="width: 100%; background-color: #f4f4f5;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0" bgcolor="#f4f4f5">
                    <tbody><tr>
                        <td align="center" style="padding: 20px;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: auto;">
                                <tbody><tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <h1 style="font-family: Arial, sans-serif; font-size: 28px; font-weight: bold; color: #1f2937; margin: 0; letter-spacing: 1px;">Kalika AI</h1>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" bgcolor="#ffffff" style="border-radius: 24px; padding: 40px 20px;">
                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <tbody><tr>
                                                <td align="center" style="padding-bottom: 10px;">
                                                    <h2 style="font-family: Arial, sans-serif; font-size: 40px; font-weight: bold; margin: 0; color: #1f2937;">
                                                        Partner with <span style="color: #2563eb;">Kalika AI</span>
                                                    </h2>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td align="center" style="padding: 10px 0 30px 0;">
                                                    <p style="font-family: Arial, sans-serif; font-size: 18px; color: #4b5563; margin: 0; max-width: 450px; line-height: 1.5;">
                                                        Dear [Recipient],<br>
                                                        As a valued partner, explore AI tools to optimize your operations and drive business growth.
                                                    </p>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td align="center" style="padding-bottom: 40px;">
                                                    <a href="https://www.kalisoftai.in/?campaign_id=[CAMPAIGN_ID]" target="_blank" style="font-size: 16px; font-weight: bold; font-family: sans-serif; color: #ffffff; text-decoration: none; border-radius: 30px; padding: 16px 32px; background-color: #2563eb; display: inline-block;">Discover Our AI Solutions</a>
                                                </td>
                                            </tr>
                                        </tbody></table>
                                    </td>
                                </tr>
                                <tr><td style="height: 20px;"></td></tr>
                                <tr>
                                    <td bgcolor="#ffffff" style="border-radius: 24px; padding: 30px 20px;">
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #1f2937; margin: 0 0 5px 0;">B2B E-commerce Ads AI</h3>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #4b5563; margin: 0; line-height: 1.5;">
                                                            Develop targeted ad campaigns to strengthen your B2B e-commerce strategies and engage potential partners.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #1f2937; margin: 0 0 5px 0;">YouTube Shorts AI</h3>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #4b5563; margin: 0; line-height: 1.5;">
                                                            Automatically identify engaging moments in long videos to create compelling short-form content for social media.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 30px 20px;">
                                        <p style="font-family: Arial, sans-serif; font-size: 14px; color: #6b7280; margin: 0 0 15px 0;">
                                            © 2025 Kalika AI. All rights reserved.<br>
                                            Sent by Kalika AI, contact@kalisoftai.in
                                        </p>
                                        <p style="font-family: Arial, sans-serif; font-size: 12px; color: #6b7280; margin: 0;">
                                            To unsubscribe, reply with "Unsubscribe".
                                        </p>
                                    </td>
                                </tr>
                            </tbody></table>
                        </td>
                    </tr>
                </tbody></table>
            </center>
        """).strip()

        templates_to_create = [
            {'name': 'KaliSoft AI - Dark Theme', 'html_content': template1_html},
            {'name': 'KaliSoft AI - Light Theme', 'html_content': template2_html},
        ]

        for template_data in templates_to_create:
            template, created = EmailTemplate.objects.update_or_create(
                name=template_data['name'],
                defaults={'html_content': template_data['html_content']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created template: "{template.name}"'))
            else:
                self.stdout.write(self.style.WARNING(f'Template "{template.name}" already exists. Updated it.'))
        
        self.stdout.write(self.style.SUCCESS('--- Seeding Complete ---'))
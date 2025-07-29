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
                                        <h1 style="font-family: Arial, sans-serif; font-size: 28px; font-weight: bold; color: #ffffff; margin: 0; letter-spacing: 1px;">KALI SOFT AI</h1>
                                    </td>
                                </tr>
                                
                                <tr>
                                    <td align="center" bgcolor="#161B22" style="border-radius: 24px; padding: 40px 20px;">
                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <tbody><tr>
                                                <td align="center" style="padding-bottom: 10px;">
                                                    <h2 style="font-family: Arial, sans-serif; font-size: 40px; font-weight: bold; margin: 0; color: #ffffff;">
                                                        A New AI Opportunity for <span style="color: #4facfe;">Kalika Suppliers</span>
                                                    </h2>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td align="center" style="padding: 10px 0 30px 0;">
                                                    <p style="font-family: Arial, sans-serif; font-size: 18px; color: #a1a9c0; margin: 0; max-width: 450px; line-height: 1.5;">
                                                        As a valued partner of Kalika Enterprises, gain exclusive access to AI tools designed to boost your sales, streamline operations, and grow your business.
                                                    </p>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td align="center" style="padding-bottom: 40px;">
                                                    <a href="https://www.kalisoftai.in/" target="_blank" style="font-size: 16px; font-weight: bold; font-family: sans-serif; color: #ffffff; text-decoration: none; border-radius: 30px; padding: 16px 32px; background-color: #8b5cf6; display: inline-block;">Explore AI Services</a>
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
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://kalikaindia.com/" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #f0f2f5; margin: 0 0 5px 0;">B2B E-commerce Ads AI</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #3b82f6;">Increase Your Sales</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #a1a9c0; margin: 0; line-height: 1.5;">
                                                            Showcase your products on the Kalika Enterprises B2B site. Our AI creates <strong style="color: #60a5fa; font-weight: normal;">eye-catching ads</strong> for your entire catalog, driving <strong style="color: #60a5fa; font-weight: normal;">more visibility and sales</strong> with zero extra effort.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;"><tbody><tr><td height="1" bgcolor="#30363d"></td></tr></tbody></table>
                                        
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://youtu.be/oMIXgF1iTy4?si=snHiWgqTDLdA33E-" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #f0f2f5; margin: 0 0 5px 0;">Procurement AI</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #8b5cf6;">Reduce Costs</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #a1a9c0; margin: 0; line-height: 1.5;">
                                                            We built ProcureAI to streamline operations for Kalika Enterprises. Now, use it to <strong style="color: #60a5fa; font-weight: normal;">optimize your own supply chain</strong> and <strong style="color: #60a5fa; font-weight: normal;">cut operational costs</strong>.
                                                        </p>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="left" style="padding-top: 15px;">
                                                        <a href="https://youtu.be/oMIXgF1iTy4?si=snHiWgqTDLdA33E-" target="_blank" style="font-size: 14px; font-family: sans-serif; color: #ffffff; text-decoration: none; border-radius: 8px; padding: 8px 16px; background-color: #4facfe; display: inline-block;">Watch Demo</a>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;"><tbody><tr><td height="1" bgcolor="#30363d"></td></tr></tbody></table>

                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://youtu.be/4vMPJtofWrs?si=XKcU22V5Slgj2xHG" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #f0f2f5; margin: 0 0 5px 0;">Marketing AI</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #18bb9c;">Find New Customers</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #a1a9c0; margin: 0; line-height: 1.5;">
                                                            Expand your business beyond Kalika Enterprises. Our AI helps you <strong style="color: #60a5fa; font-weight: normal;">find new buyers</strong> and generate <strong style="color: #60a5fa; font-weight: normal;">professional outreach emails</strong> automatically.
                                                        </p>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="left" style="padding-top: 15px;">
                                                        <a href="https://youtu.be/4vMPJtofWrs?si=XKcU22V5Slgj2xHG" target="_blank" style="font-size: 14px; font-family: sans-serif; color: #ffffff; text-decoration: none; border-radius: 8px; padding: 8px 16px; background-color: #4facfe; display: inline-block;">Watch Demo</a>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;"><tbody><tr><td height="1" bgcolor="#30363d"></td></tr></tbody></table>

                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://www.kalisoftai.in/projects" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #f0f2f5; margin: 0 0 5px 0;">Internal PO Automation</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #f59e0b;">Save Time</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #a1a9c0; margin: 0; line-height: 1.5;">
                                                            <strong style="color: #60a5fa; font-weight: normal;">Parse POs from Gmail</strong>, extract material needs with AI, and <strong style="color: #60a5fa; font-weight: normal;">manage stock status</strong> internally.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;"><tbody><tr><td height="1" bgcolor="#30363d"></td></tr></tbody></table>

                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://www.kalisoftai.in/projects" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #f0f2f5; margin: 0 0 5px 0;">Cinematic Video AI</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #ec4899;">Creative</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #a1a9c0; margin: 0; line-height: 1.5;">
                                                        Turn images into <strong style="color: #60a5fa; font-weight: normal;">stunning cinematic videos</strong> with AI captions, music, and cloud delivery.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;"><tbody><tr><td height="1" bgcolor="#30363d"></td></tr></tbody></table>

                                        <table width="100%" border="0" cellpadding="0" cellspacing="0">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://www.youtube.com/watch?v=KhX-NCDNcuk" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #f0f2f5; margin: 0 0 5px 0;">YouTube Shorts AI</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #ef4444;">Content</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #a1a9c0; margin: 0; line-height: 1.5;">
                                                            Automatically <strong style="color: #60a5fa; font-weight: normal;">find viral moments</strong> in long videos and generate <strong style="color: #60a5fa; font-weight: normal;">engaging shorts</strong> for social media.
                                                        </p>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="left" style="padding-top: 15px;">
                                                        <a href="https://www.youtube.com/watch?v=KhX-NCDNcuk" target="_blank" style="font-size: 14px; font-family: sans-serif; color: #ffffff; text-decoration: none; border-radius: 8px; padding: 8px 16px; background-color: #4facfe; display: inline-block;">Watch Now</a>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </td>
                                </tr>

                                <tr>
                                    <td align="center" style="padding: 30px 20px;">
                                        <p style="font-family: Arial, sans-serif; font-size: 14px; color: #a1a9c0; margin: 0 0 15px 0;">
                                            © 2024 Kali Soft AI. All rights reserved.<br
                                        </p>
                                        <p style="font-family: Arial, sans-serif; font-size: 14px; color: #a1a9c0; margin: 0 0 15px 0;">
                                            <a href="#" target="_blank" style="color: #a1a9c0; text-decoration: underline;">LinkedIn</a> &nbsp;|&nbsp;
                                            <a href="#" target="_blank" style="color: #a1a9c0; text-decoration: underline;">Twitter/X</a>
                                        </p>
                                        <p style="font-family: Arial, sans-serif; font-size: 12px; color: #a1a9c0; margin: 0;">
                                            If you no longer wish to receive these emails, you can <a href="#" target="_blank" style="color: #4facfe; text-decoration: underline;">unsubscribe here</a>.
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
            <center style="width: 100%; background-color: #f4f7f6;">
                <table width="100%" border="0" cellpadding="0" cellspacing="0" bgcolor="#f4f7f6">
                    <tbody><tr>
                        <td align="center" style="padding: 20px;">
                            <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: auto;">
                                <tbody><tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <h1 style="font-family: Arial, sans-serif; font-size: 28px; font-weight: bold; color: #1a202c; margin: 0; letter-spacing: 1px;">KALI SOFT AI</h1>
                                    </td>
                                </tr>
                                
                                <tr>
                                    <td align="center" bgcolor="#ffffff" style="border-radius: 24px; padding: 40px 20px; border: 1px solid #e2e8f0;">
                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <tbody><tr>
                                                <td align="center" style="padding-bottom: 10px;">
                                                    <h2 style="font-family: Arial, sans-serif; font-size: 40px; font-weight: bold; margin: 0; color: #1a202c;">
                                                        A New AI Opportunity for <span style="color: #4299e1;">Kalika Suppliers</span>
                                                    </h2>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td align="center" style="padding: 10px 0 30px 0;">
                                                    <p style="font-family: Arial, sans-serif; font-size: 18px; color: #4a5568; margin: 0; max-width: 450px; line-height: 1.5;">
                                                        As a valued partner of Kalika Enterprises, gain exclusive access to AI tools designed to boost your sales, streamline operations, and grow your business.
                                                    </p>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td align="center" style="padding-bottom: 40px;">
                                                    <a href="https://www.kalisoftai.in/" target="_blank" style="font-size: 16px; font-weight: bold; font-family: sans-serif; color: #ffffff; text-decoration: none; border-radius: 30px; padding: 16px 32px; background-color: #8b5cf6; display: inline-block;">Explore AI Services</a>
                                                </td>
                                            </tr>
                                        </tbody></table>
                                    </td>
                                </tr>
                                
                                <tr><td style="height: 20px;"></td></tr>

                                <tr>
                                    <td bgcolor="#ffffff" style="border-radius: 24px; padding: 30px 20px; border: 1px solid #e2e8f0;">
                                        
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://kalikaindia.com/" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #2d3748; margin: 0 0 5px 0;">B2B E-commerce Ads AI</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #3b82f6;">Increase Your Sales</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #4a5568; margin: 0; line-height: 1.5;">
                                                            Showcase your products on the Kalika Enterprises B2B site. Our AI creates <strong style="color: #4299e1; font-weight: normal;">eye-catching ads</strong> for your entire catalog, driving <strong style="color: #4299e1; font-weight: normal;">more visibility and sales</strong> with zero extra effort.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;"><tbody><tr><td height="1" bgcolor="#e2e8f0"></td></tr></tbody></table>
                                        
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://youtu.be/oMIXgF1iTy4?si=snHiWgqTDLdA33E-" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #2d3748; margin: 0 0 5px 0;">Procurement AI</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #8b5cf6;">Reduce Costs</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #4a5568; margin: 0; line-height: 1.5;">
                                                            We built ProcureAI to streamline operations for Kalika Enterprises. Now, use it to <strong style="color: #4299e1; font-weight: normal;">optimize your own supply chain</strong> and <strong style="color: #4299e1; font-weight: normal;">cut operational costs</strong>.
                                                        </p>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="left" style="padding-top: 15px;">
                                                        <a href="https://youtu.be/oMIXgF1iTy4?si=snHiWgqTDLdA33E-" target="_blank" style="font-size: 14px; font-family: sans-serif; color: #ffffff; text-decoration: none; border-radius: 8px; padding: 8px 16px; background-color: #4299e1; display: inline-block;">Watch Demo</a>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;"><tbody><tr><td height="1" bgcolor="#e2e8f0"></td></tr></tbody></table>

                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://youtu.be/4vMPJtofWrs?si=XKcU22V5Slgj2xHG" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #2d3748; margin: 0 0 5px 0;">Marketing AI</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #18bb9c;">Find New Customers</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #4a5568; margin: 0; line-height: 1.5;">
                                                            Expand your business beyond Kalika Enterprises. Our AI helps you <strong style="color: #4299e1; font-weight: normal;">find new buyers</strong> and generate <strong style="color: #4299e1; font-weight: normal;">professional outreach emails</strong> automatically.
                                                        </p>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="left" style="padding-top: 15px;">
                                                        <a href="https://youtu.be/4vMPJtofWrs?si=XKcU22V5Slgj2xHG" target="_blank" style="font-size: 14px; font-family: sans-serif; color: #ffffff; text-decoration: none; border-radius: 8px; padding: 8px 16px; background-color: #4299e1; display: inline-block;">Watch Demo</a>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;"><tbody><tr><td height="1" bgcolor="#e2e8f0"></td></tr></tbody></table>

                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://www.kalisoftai.in/projects" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #2d3748; margin: 0 0 5px 0;">Internal PO Automation</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #f59e0b;">Save Time</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #4a5568; margin: 0; line-height: 1.5;">
                                                            <strong style="color: #4299e1; font-weight: normal;">Parse POs from Gmail</strong>, extract material needs with AI, and <strong style="color: #4299e1; font-weight: normal;">manage stock status</strong> internally.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;"><tbody><tr><td height="1" bgcolor="#e2e8f0"></td></tr></tbody></table>

                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://www.kalisoftai.in/projects" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #2d3748; margin: 0 0 5px 0;">Cinematic Video AI</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #ec4899;">Creative</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #4a5568; margin: 0; line-height: 1.5;">
                                                        Turn images into <strong style="color: #4299e1; font-weight: normal;">stunning cinematic videos</strong> with AI captions, music, and cloud delivery.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 15px;"><tbody><tr><td height="1" bgcolor="#e2e8f0"></td></tr></tbody></table>

                                        <table width="100%" border="0" cellpadding="0" cellspacing="0">
                                            <tbody>
                                                <tr>
                                                    <td>
                                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td>
                                                                        <a href="https://www.youtube.com/watch?v=KhX-NCDNcuk" target="_blank" style="text-decoration: none;">
                                                                            <h3 style="font-family: Arial, sans-serif; font-size: 22px; font-weight: bold; color: #2d3748; margin: 0 0 5px 0;">YouTube Shorts AI</h3>
                                                                        </a>
                                                                    </td>
                                                                    <td align="right" valign="top">
                                                                        <span style="font-family: sans-serif; font-size: 13px; font-weight: bold; padding: 5px 12px; border-radius: 20px; color: #fff; background-color: #ef4444;">Content</span>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="padding-top: 5px;">
                                                        <p style="font-family: Arial, sans-serif; font-size: 15px; color: #4a5568; margin: 0; line-height: 1.5;">
                                                            Automatically <strong style="color: #4299e1; font-weight: normal;">find viral moments</strong> in long videos and generate <strong style="color: #4299e1; font-weight: normal;">engaging shorts</strong> for social media.
                                                        </p>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="left" style="padding-top: 15px;">
                                                        <a href="https://www.youtube.com/watch?v=KhX-NCDNcuk" target="_blank" style="font-size: 14px; font-family: sans-serif; color: #ffffff; text-decoration: none; border-radius: 8px; padding: 8px 16px; background-color: #4299e1; display: inline-block;">Watch Now</a>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </td>
                                </tr>

                                <tr>
                                    <td align="center" style="padding: 30px 20px;">
                                        <p style="font-family: Arial, sans-serif; font-size: 14px; color: #718096; margin: 0 0 15px 0;">
                                            © 2024 Kali Soft AI. All rights reserved.<br>
                                        </p>
                                        <p style="font-family: Arial, sans-serif; font-size: 14px; color: #718096; margin: 0 0 15px 0;">
                                            <a href="#" target="_blank" style="color: #718096; text-decoration: underline;">LinkedIn</a> &nbsp;|&nbsp;
                                            <a href="#" target="_blank" style="color: #718096; text-decoration: underline;">Twitter/X</a>
                                        </p>
                                        <p style="font-family: Arial, sans-serif; font-size: 12px; color: #718096; margin: 0;">
                                            If you no longer wish to receive these emails, you can <a href="#" target="_blank" style="color: #4299e1; text-decoration: underline;">unsubscribe here</a>.
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
            # Use update_or_create to avoid creating duplicates if the command is run again.
            template, created = EmailTemplate.objects.update_or_create(
                name=template_data['name'],
                defaults={'html_content': template_data['html_content']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created template: "{template.name}"'))
            else:
                self.stdout.write(self.style.WARNING(f'Template "{template.name}" already exists. Updated it.'))
        
        self.stdout.write(self.style.SUCCESS('--- Seeding Complete ---'))

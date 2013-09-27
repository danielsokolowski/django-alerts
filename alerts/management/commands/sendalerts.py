from django.core.management.base import BaseCommand, CommandError
from alerts.models import Alert
from alerts.models import AlertManager

class Command(BaseCommand):
	args = ''
	help = 'Sends out (currently emails only) new alerts since last run as needed (based on "status" and' \
			' "last_run" fields). It is recommended this be called by the OS itself, for example as a CRON job' \
			' with a frequency no slower than "{0}" minutes as defined by "AlertManager.FREQUENCY_DEFAULT".' \
			' For a sample cron.d file that can be symlinked see "alerts/alerts-cron.d-entry*".' \
			.format(AlertManager.FREQUENCY_DEFAULT) 

	def handle(self, *args, **options):
		emails_sent_total = 0
		items_new_total = 0
		alert_queryset = Alert.objects.active()
		alert_total = alert_queryset.count()
		alert_current = 1 # used as loop counter
		
		self.stdout.write('Starting to process "{0}" alerts.'.format(alert_total))
		for alert in alert_queryset:
			items_new = alert.send_email()
			self.stdout.write(' - {0}/{1}. processed "{2}" which resulted in "{3}" new item(s).'.format(
																						alert_current,
																						alert_total,
																						alert.name, 
																						items_new))
			alert_current += 1
			items_new_total += items_new
			if items_new > 0: emails_sent_total += 1
		self.stdout.write('Finished processing "{0}" alerts which resulted in "{1}" emails and "{2}" new items' \
						' (includes duplicates) found since last run.'.format(alert_total, emails_sent_total, items_new_total))
		
			
from django.db import models
#from django.contrib.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.core.exceptions import ValidationError
import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
import settings
from django.contrib.contenttypes.models import ContentType
import sys
from django.utils import simplejson, timezone
from django.conf import settings
from django.core.urlresolvers import reverse
logger = logging.getLogger(__name__)



class AlertManager(models.Manager):
	"""
	Additional methods / constants to Alert's objects manager:
	
	``AlertManager.objects.public()`` - all instances that are asccessible through front end
	``AlertManager.objects.active()`` - all instances that are considered `active` -  i.e. aviable in forms, selections, choices, etc
	"""
	### Model (db table) wide constants - we put these and not in model definition to avoid circular imports.
	### One can access these constants through <Nofoo>.objects.STATUS_DISABLED or ImageManager.STATUS_DISABLED
	# The order to status is logical progression from low to high and so higher status implies superset of lower status
	# that is you should have STATUS_MODERATED for an instance that is not displayed - since STATUS_ENABLED is implied
	# TODO: make it a bitmask status like field?
	STATUS_DISABLED = 0 # standarized - means accross models and projects so do not change rather disable
	#STATUS_DECLINED = 1  
	#STATUS_ENABLED= 10 # grandfathered - replicated by STATUS_ACTIVE
	STATUS_ACTIVE = 11 # standarized - we don't need STATUS_ENALBED because _ACTIVE can be enabled or active 
					   # (takes date into consideration) as needed  
	#STATUS_MODERATED = 100 # standarized (but yes - we could have approved but not moderated this is the more sane order)
	#STATUS_APPROVED = 101 
	#STATUS_FINALIZED = 200
	#STATUS_FINALIZED_POSTER = 201
	#STATUS_FINALIZED_BIDDER = 202 # TODO: do we need this? we can quickly check by looking at required fields
	STATUS_ARCHIVED = 1000 # standarized
	STATUS_CHOICES = (
		# add choices as needed
		(STATUS_DISABLED, "Disabled"),
		#(STATUS_ENABLED, "Enabled"),
		(STATUS_ACTIVE, 'Active'), 
		#(STATUS_MODERATED, 'Moderated'), 
		(STATUS_ARCHIVED, "Archived"),
	)
	FREQUENCY_DEFAULT = 15 # in minutes - IT"S important that this is the fastest value too as we use this to state
						   # the minimum call time in the help of send_alerts command
	FREQUENCY_CHOICES = (
						#'0', 'As soon as possible'
						#'5', 'Every 5 minutes'
						(FREQUENCY_DEFAULT, 'Check every 15 minutes'),
						(30, 'Check every 30 minutes'),
						(60, 'Check once an hour'),
						(360, 'Check every six hours'),
						(1440, 'Check once a day'),
						)
	
	# for an item to be public,active etc it's parent must be active/public as well so we use a bit of list 
	# comperhansion because you can't yet chain custom manager filters ex: 'public().open()'. So we provide access 
	# by defining the QUERYSET's whcih also we can use directly in 'ForeignKey.limit_choices_to' arguments
	# workaround - http://stackoverflow.com/questions/2163151/custom-queryset-and-manager-without-breaking-dry
	# comperhension to skip some code repetition
	QUERYSET_PUBLIC_KWARGS = {'status__gte': STATUS_DISABLED}
	# lets take the parent into consideration
	#QUERYSET_PUBLIC_KWARGS.update(dict([('offer__' + i[0], i[1]) \
	#								for i in OfferManager.QUERYSET_PUBLIC_KWARGS.iteritems()])) 
	#UERYSET_DECLINED_KWARGS = {'status': STATUS_DECLINED}
	#QUERYSET_DECLINED_KWARGS.update(dict([('offer__' + i[0], i[1]) \
	#								for i in OfferManager.QUERYSET_PUBLIC_KWARGS.iteritems()]))
	QUERYSET_ACTIVE_KWARGS = {'status': STATUS_ACTIVE} #TODO: I think we need to rename everything to STATUS_ACTIVE this active/enabled distincion is a little kluge
	#QUERYSET_ACTIVE_KWARGS.update(dict([('offer__' + i[0], i[1]) \
	#								for i in OfferManager.QUERYSET_PUBLIC_KWARGS.iteritems()])) 
	#QUERYSET_MODERATED_KWARGS = {'status': STATUS_MODERATED}
	#QUERYSET_DECLINED_KWARGS.update(dict([('offer__' + i[0], i[1]) \
	#								for i in OfferManager.QUERYSET_PUBLIC_KWARGS.iteritems()]))
	
	def public(self):
		""" Returns all entries someway accessible through front end site - think twice about changing the queryset for this"""
		return self.filter(**self.QUERYSET_PUBLIC_KWARGS)
	public.chainable = True # FIXME: use the updated ticket rather then my own
	
	def active(self):
		""" Returns all entries that are considered active, i.e. aviable in forms, selections, choices, etc """
		return self.filter(**self.QUERYSET_ACTIVE_KWARGS)
	active.chainable = True # FIXME: use the updated ticket rather then my own
	

class Alert(models.Model):
	"""
	Alerts are stored as QuerySet kwargs and are triggered on save signal
	and  if the executed query as specified by in the queryset_filter_kwargs AND 
	.filter(pk__gt = self.latest_object.pk) returns  a non null value. returns an object
	
	NOTE: specifing the complete QuerySet as a string was deemed insecure, ex. 
		  User.objects.all().delete() so we use kwargs instead
	
	** OLD **
	Main entity representing Alertn object, a django Query API is stored as string
	and executed as such, the last run's pk (id) is store so that on subsequent runs we can
	notify of new entries and not the whole list again.
	
	We are storing the query as a string so that we have a lot of flexebility such as
	being able to do advanced things like Q() objects or | or & QuerySet results
	ex. User.object.all(...) & User.objects.filter(..)  
	"""
	### model options - "anything that's not a field"
	class Meta:
		#ordering = ['order', 'name']
		#get_latest_by = 'order'
		#order_with_respect_to = <some FK to parent model>
		#permissions = [["can_deliver_pizzas", "Can deliver pizzas"]]
		unique_together = [["user", "queryset_filter_kwargs"]]
		#verbose_name = "pizza"
		#verbose_name_plural = "stories"
	
	### Django establshed methods
	def __unicode__(self):
		return u'{0}{1} [{2}]'.format(self.get_pk_display() + ': ' if settings.DEBUG else '', self.name, 
										self.get_status_display())
		
	def get_absolute_url(self):
		""" Returns the relative url mapping for the instance of this model if it exists or None otherwise"""
		# see for 'gotchas': https://docs.djangoproject.com/en/dev/ref/unicode/#taking-care-in-get-absolute-url
		return reverse('AlertUpdateView', kwargs={'pk': self.pk})
	
	def clean(self):
		try:
			self.latest_object_content_type
		except:
			raise ValidationError('Please specify "latest_object_content_type", error: {0}.'.format(sys.exc_info()[1]))
		
		# ensure referenced model uses expected AutoIngeterField for it's PK
		if type(self.latest_object_content_type.model_class()._meta.pk) != models.AutoField:
			raise ValidationError('Alerts currently only support models defined with a primary keys as AutoField,' \
				' but referenced model uses "{0}".'.format(type(self.latest_object_content_type.model_class()._meta.pk)))
			
		# Ensure our query_filter_kwargs is a valid one
		try: 
			self.latest_object_content_type.model_class().objects.filter(**simplejson.loads(self.queryset_filter_kwargs))
		except:
			raise ValidationError('Provided "{0}" filter queryset **kwargs dictionary generated following error: {1}' \
							.format(self.queryset_filter_kwargs, sys.exc_info()[1]))
		
	def save(self, *args, **kwargs):
		# if last_run and latest_pk not specified fill it in because otherwise it will email the entire list to end user
		# when send_emails is called - if it is specified then we trust the programmer (me) knows why they did it
		#if self.last_run == None:
		#	self.last_run = timezone.now()
		#if self.latest_object_pk == None:
		#	queryset = self.latest_object_content_type.model_class().objects\
		#		.filter(**simplejson.loads(self.queryset_filter_kwargs)).order_by('-pk')
		#	if queryset.count() > 0:
		#		self.latest_object_pk = queryset[:1][0].pk
		super(Alert, self).save(*args, **kwargs)
		
	### extra model functions
	def send_email(self):
		""" 
		Checks and if needed sends a notification to specified user for this alert, returns the number of 
		new entries found since last run.
		
		FIXME: refactor this out and move this onto the model level where we group by content_type and query and do 
			   one database hit and loop over individual user entries to generate multiple bcc list
		"""
		assert  self.latest_object_content_type.model_class(), ""
		
		# don't run if status is disabled
		if self.status == AlertManager.STATUS_DISABLED:
			logger.debug('Skipping "{0}" alert due to status'.format(self))
			return 0
		
		# don't run if timing is not right
		if (timezone.now() - self.last_run).total_seconds <= self.frequency * 60: 
			logger.debug('Skipping "{0}" alert as frequency alert not reached'.format(self))
			return 0
		
		# self update first to minimize (not prevent) race conditions
		self.last_run = timezone.now()
		self.save()
		
		# get  entries
		queryset = self.latest_object_content_type.model_class().objects.all() # remember django lazly executes this
		queryset_filter_kwargs = simplejson.loads(self.queryset_filter_kwargs) 	# we must have STR based dictionary 
																				# but django deals in unicode and so 
																				# our mapping results in u'keys'
		#queryset_filter_kwargs = {str(k): v for k, v in queryset_filter_kwargs.items()}
		queryset = queryset.filter(**queryset_filter_kwargs) # apply filters
		del queryset_filter_kwargs # keep scope tidy
		
		if self.latest_object_pk != None: # get newer entries only
			queryset = queryset.filter(pk__gt = self.latest_object_pk) #TODO: should we make this .public(), .all() or provide a way to specify this?
		
		
		# now that we have our list send a notification
		logger.info('Executing notification "{0}" which found "{1}" new item(s) since last run "{2}".' \
						.format(self, queryset.count(), self.last_run))
		
		# no new entries so stop
		if queryset.count() == 0:
			return 0
		
		# send the email
		send_mail('Alert "%s": %s new item(s) since %s' % (self.name, queryset.count(), self.last_run), 
				   render_to_string('{0}/email_alert_{1}_{2}.txt'.format(
											self._meta.app_label,
											self.latest_object_content_type.model_class()._meta.app_label,
											self.latest_object_content_type.model_class()._meta.object_name.lower()
											),
										{'alert': self,
										'user': self.user, 
										'queryset': queryset,
										'SITE_URL': settings.SITE_URL
										}), 
										# FIXME: we have a problem we can't pass the Site domain to our template
				   from_email = settings.EMAIL_HOST_USER,
				   recipient_list = [self.user.email],
				   fail_silently=True, 
				   connection=None)
		
		# self update properly now - we update the lastrun again to account for emailing time.
		self.latest_object = queryset[:1][0]
		self.last_run = timezone.now()
		self.save()
		
		return queryset.count()
		
	
	### custom managers
	objects = AlertManager()
	#objects = models.GeoManager() # geodjango objects manager
	
	### model DB fields
	status = models.IntegerField(choices=AlertManager.STATUS_CHOICES, default=AlertManager.STATUS_ACTIVE)
	# do we need a trigger type signal ?
	# trigger = models.CharField(<choices>)
	name = models.CharField(help_text='Alert name.', max_length=255)
	
	user = models.ForeignKey(User, help_text="Recipient of this alert") # TODO: many to many not a good option becuase what if user wants to have send the alerts once a day? we could use the status field and last run field for that.
										# TODO: this is used for who owns it or just the email to send this to? 
										# TODO: or do we make it manytomany! - yes the latter seems to be more efficient
										# TODO: also what if the user does NOT want to recieve notifications any more do we just delete it? or have intermediate model with status
	frequency = models.PositiveIntegerField(choices=AlertManager.FREQUENCY_CHOICES, default=AlertManager.FREQUENCY_DEFAULT)
	last_run = models.DateTimeField(blank=True, null=True)
	
	latest_object_content_type = models.ForeignKey(ContentType, help_text='The "Model" the QuerySet filter is executed against.')
	latest_object_pk = models.PositiveIntegerField(blank=True, null=True, help_text='This doubles as the PK of the last object found when query was run, and is used by GenericForeginKey which will return "NoneType" if it is not set.')
	latest_object = generic.GenericForeignKey('latest_object_content_type', 'latest_object_pk')
	
	queryset_filter_kwargs = models.TextField(help_text='The parameters (if any) as a JSON serialized dict to be use for the filter query; default to "{}"'
											,blank=False, default='{}') # TODO: this is dangerous how to sterlize it? we can execute the command like User.objects.all().delete()!
	
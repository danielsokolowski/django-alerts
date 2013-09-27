from django.views.generic.edit import UpdateView, CreateView
from guardian.mixins import PermissionRequiredMixin
from alerts import forms as alert_forms # we import all defined forms
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from alerts.models import Alert
from django.contrib import messages
from django.core import urlresolvers

from django.views.generic.base import RedirectView
from django.contrib import messages
from django.contrib.sites.models import get_current_site

class  AlertIndexView(RedirectView):
	"""
	Temporary place holder redirect view for  AlertIndexView
	"""
	permanent = False
	
	def get_redirect_url(self, **kwargs):
		try:
			return Alert.objects.active().filter(user__pk = self.request.user.pk).order_by('-pk')[:1][0].get_absolute_url()
		except:
			return urlresolvers.reverse("AlertCreateView")
		

class AlertCreateView(CreateView):
	"""
	OfferCreateView public facing to create offers
	
	TODO: create an intermediate form since we don't know 'content type' object so we don't know the tempalte to use yet
			this is a wish list - as for now we only have alert offer
	"""
	### TemplateResponseMixin
	template_name = 'alerts/alert-create-view.html'
	### CreateView
	
	### SingleObjectMixin
	model = Alert
	
	### FormMixing settings
	#initial = {}
	form_class = alert_forms.AlertOfferCreateForm
	#success_url = None
	
	### ModelFormMixin
	def get_success_url(self):
		messages.success(self.request, 'Your "{0}" alert was created'.format(self.object))
		return super(AlertCreateView, self).get_success_url() # should call object.get_absolute_url
	
	def get_form_kwargs(self):
		kwargs = super(AlertCreateView, self).get_form_kwargs()
		kwargs.update({'user': self.request.user})
		return kwargs

class AlertUpdateView(UpdateView): #LoginRequired check is perfromed in dispatch directly 
	"""  Update view for a Company instance. """

	### PermissionRequiredMixin
	permission_required = 'companies.change_company'

	### TemplateResponseMixin
	template_name = 'alerts/alert-update-view.html' # default is auth/user_detail.html because we are using the User model not Company
	
	### SingleObjectMixin
	#context_object_name = "user_object"
	queryset = Alert.objects.none() # we greedly limit the query to NONE and return only the user's alerts when necessary
	slug_field = 'user__username' # it's guranteed to be unique by db design
	slug_url_kwarg = 'username' # our url pattern capture group is put in kwarg under this name
	#context_object_name = 'user' # defaults to object model name lower case

	### FormMixin
	form_class = alert_forms.AlertOfferUpdateForm # default form for our User model

	### SingleObjectMixin
	def get_queryset(self):
		""" greedly limit alerts to only active and by user requesting the view """
		return Alert.objects.active().filter(user__pk=self.request.user.pk) # stupid lazyuser object so we explicitly do the match against pk

	### ModelFormMixin
	def get_form_class(self):
		"""
		Based on the 'latest_object_content_type' we return the form class named 'Alert<model class>Form' which 
		we accomplish by auto importing everything from 'alerts.forms' and if the form is not defined we 
		grecefuly error/degrade (TODO: how will we error out a generic - readonly form?)
		"""
		desired_form_klass_name = u"Alert{0}UpdateForm".format(
			ContentType.objects.get(app_label=self.object.latest_object_content_type.app_label,
									model=self.object.latest_object_content_type.model)\
									.model_class().__name__) 
									# let's assume our custom form is to be used for creation and updating  
		return getattr(alert_forms, desired_form_klass_name)
		try:
			return getattr(alert_forms, desired_form_klass_name)
		except AttributeError:
			return self.form_class

	### SingleObjectMixin (in eclise you can CTRL+Click on the name to go to file)
	def get_context_data(self, **kwargs):
		context = super(AlertUpdateView, self).get_context_data(**kwargs)
		context['alert_list'] =  self.get_queryset()
		return context
	
	### View (in eclipse you can CTRL+Click on the keyword 'View' to go to file)
	@method_decorator(login_required)
	def dispatch(self, request, *args, **kwargs):
		return super(AlertUpdateView, self).dispatch(request, *args, **kwargs)

	### ModelFormMixin
	def get_success_url(self):
		messages.success(self.request, 'Your "{0}" alert was updated'.format(self.object))
		return super(AlertUpdateView, self).get_success_url() # should call object.get_absolute_url
from django import forms
from django.template.loader import render_to_string
from django.conf import settings
from alerts.models import Alert
from offers.models import OfferManager, QualityGrade, Offer
from products.models import Product
from geonames.models import Country, Currency
from html5monkeypatch import html5_wigets
from django.core.exceptions import ValidationError
from django.utils import simplejson, timezone
from django.contrib.contenttypes.models import ContentType
from django.forms import widgets

class  AlertDefaultForm(forms.ModelForm):
	pass 

class  AlertOfferUpdateForm(forms.ModelForm): 
	""" should shadow the search form but we can't extend directly because of subcategories for example """
	# configuration
	class Meta:
		model =  Alert
		fields = ('status', 'name', 'frequency', 'type', 'product__pk', 'quality_grade__pk', 'origin_country__pk', 'currency__pk', 'ship_from_country__pk'
				  ,'ship_to_countries__pk', 'amount_unit', 'amount_min__gte', 'amount_max__lte') # show these fields from model
		#exclude = () # exclude these fields from model
			#widgets = {'type': forms.widgets.RadioSelect(), 'company': forms.widgets.RadioSelect(), 
		#		   'shipping_term': forms.widgets.RadioSelect(), '#payment_term': forms.widgets.RadioSelect(), 
		#		   'amount_unit': forms.widgets.RadioSelect()}
	
	class CurrencyModelChoiceField(forms.models.ModelChoiceField):
		""" Modified to display as "Code + Name" """
		def label_from_instance(self, obj):
			# Clone and put on Python path: https://github.com/tenXer/PyDevSrc, place this in your settings_development.py, and place your 'break' points in Eclipse
			return "{0[code]} - {0[name]}".format(forms.models.model_to_dict(obj))

	
	#error_css_class = 'clsError' # defaults to .error class
	#required_css_class = 'clsRequired'   # defauts to nothing - but keep in mind we have a patch that auto adds '.required' class
	
	### default model form fields over rides or more fields
	# in our case we should match our queryset arguement names to field names i.e. product__pk - so for 
	# foreign keys make the field name foo__pk - django will still map an instance to it's .pk value when needed
	type = forms.ChoiceField(choices=(OfferManager.TYPE_CHOICES), required=True, widget=forms.widgets.RadioSelect)
	product__pk = forms.ModelChoiceField(queryset=Product.objects.moderated_products(), required=True) # we don't need .active
	#include_subproducts = forms.BooleanField(initial=True, required=False)
	quality_grade__pk = forms.ModelChoiceField(queryset=QualityGrade.objects.active(), empty_label="Any", required=False)
	#description = forms.CharField(max_length=50, help_text='ex. Whole Sour (limited to what is selected)', required=False)
	origin_country__pk = forms.ModelChoiceField(queryset=Country.objects.active(), empty_label="Any", required=False)
	currency__pk = CurrencyModelChoiceField(queryset=Currency.objects.active(), empty_label="Any", required=False)#widget=forms.widgets.RadioSelect) 
	ship_from_country__pk = forms.ModelChoiceField(queryset=Country.objects.active(), empty_label="Any", required=False)
	ship_to_countries__pk = forms.ModelChoiceField(queryset=Country.objects.active(), empty_label="Any", required=False)
	
	amount_unit = forms.ChoiceField(required=False, 
								choices=[("", "Any")] + list(OfferManager.AMOUNT_UNIT_CHOICES), # our Any is empty value equivalent
								initial="",
								widget=forms.widgets.RadioSelect,)
	
	amount_min__gte = forms.IntegerField(required=False, help_text=('ex. 5000, or leave blank for Any'), widget=html5_wigets.NumberInput(attrs={'step': 100}))
	amount_max__lte = forms.IntegerField(required=False, help_text=('ex. 10000, or leave blank for Any'), widget=html5_wigets.NumberInput(attrs={'step': 100}))
														
	### Additional methods
	#n/a
	
	### Default django methods
	def __init__(self, *args, **kwargs):
		super(AlertOfferUpdateForm, self).__init__(*args, **kwargs)
		# grab the query_kwargs and map them onto our fields - piping it through django's form field 
		# mechanisms prevents malicious query injections on save
		for key, value in simplejson.loads(self.instance.queryset_filter_kwargs).iteritems():
			# some data stored in our queryset_filter_kwargs we don't map to a form but append on saves and such
			# so only do it for things we don't error out
			try:
				self.fields[key].initial = value
			except KeyError:
				#TODO: do we perhaps capture the erroring ones and re-add them in save() ? I think no because
				#if we update this code any 'old' alerts would get cleaned at least a little - the only benefit of that
				#would be code DRY/coolnes but that's over doing it.'
				pass
	
	
	### Field combination cleaning 
	### see https://docs.djangoproject.com/en/dev/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
	def clean(self):
		raise_validation_error = False # we will raise form level error if this is True
		cleaned_data = super(AlertOfferUpdateForm, self).clean()
		#TODO: streamline these tests and those for search form as well
		## If any amount or price per unit is specified ensure amount unit is also specified"""
		if cleaned_data['amount_unit'] in self.fields['amount_unit'].empty_values \
				 and (cleaned_data['amount_min__gte'] not in self.fields['amount_min__gte'].empty_values or \
					  cleaned_data['amount_max__lte'] not in self.fields['amount_max__lte'].empty_values):
			self._errors['amount_unit'] = self.error_class(["Amount unit can not be 'Any' when either a minimum, or maximum" \
								  " amount is specified."])
			#del cleaned_data['amount_unit']  still needed for further tests down the line FIXME: consolidate/clean this up
			raise_validation_error = True
		
		## if we are selling ensure that amounts and price if filled
		if cleaned_data['type'] == OfferManager.TYPE_SELL:
			if cleaned_data['amount_unit'] in self.fields['amount_unit'].empty_values:
				self._errors['amount_unit'] = self.error_class(["Amount unit can not be 'Any' for 'Sell' offer alerts"]) # needed so that {{form.field.errors}} renders as default UL list otherwise it's an python list
				#del cleaned_data['amount_unit'] # need it down below
				raise_validation_error = True
			if cleaned_data['amount_min__gte'] in self.fields['amount_min__gte'].empty_values:
				self._errors['amount_min__gte'] = self.error_class(["Amount minimum must be specified for 'Sell' offer alerts"])
				#del cleaned_data['amount_min__gte'] # need it for down below
				raise_validation_error = True
			if cleaned_data['amount_max__lte'] in self.fields['amount_max__lte'].empty_values:
				self._errors['amount_max__lte'] = self.error_class(["Amount maximum must be specified for 'Sell' offer alerts"])
				#del cleaned_data['amount_max__lte']
				raise_validation_error = True
#			if cleaned_data['price_per_unit'] in self.fields["price_per_unit"].empty_values:
#				self._errors["price_per_unit"] = self.error_class(["Price per unit must be specified when you are posting a for 'Sell' offer"])
#				del cleaned_data["price_per_unit"]
#				raise_validation_error = True
			
		## ansure amount_min < amount_max if they are specific
		if (cleaned_data['amount_min__gte'] not in self.fields['amount_min__gte'].empty_values and \
			cleaned_data['amount_max__lte'] not in self.fields['amount_max__lte'].empty_values) and \
			cleaned_data['amount_min__gte'] > cleaned_data['amount_max__lte']:
				self._errors['amount_min__gte'] = self.error_class(["Minimum amount can not be bigger than maximum amount."])
				del cleaned_data['amount_min__gte']
				del cleaned_data['amount_min__lte']
				raise_validation_error = True
		
		# did we have errors?
		if raise_validation_error == True:
			raise ValidationError('Please review and correct below errors.') # let's raise a form level errors
						
		return cleaned_data 
	
	def save(self, commit=True):
		m = super(AlertOfferUpdateForm, self).save(commit = False)
		queryset_filter_kwargs = {}
		for key, value in self.cleaned_data.iteritems():
			if key not in [f.name for f in self._meta.model._meta.fields] \
				and value not in self.fields[key].empty_values: # build queryset only on fields that are NOT on alerts
				try:													   # otherwise you get Alert fields being part as well
					queryset_filter_kwargs[key] = value.pk #dirty but prob best way to store the pk value rather
													   	# then the object as simplejson chokes and can not serialize
				except AttributeError:
					queryset_filter_kwargs[key] = value
			
		# add some default sane filters that we don't allow to be changed through the front by the end user
		queryset_filter_kwargs.update(OfferManager.QUERYSET_ACTIVE_KWARGS) # add public active queryset_kwargs
		# exclude the user Offers
		#FIXME: there is no foo__pk__not filter so we would have to add qaueryset_exclude_kwargs to our alerts! 
		m.queryset_filter_kwargs = simplejson.dumps(queryset_filter_kwargs)
		
		# it logically makes sense that on any change of alert through front end we reset the latest and last run
		queryset = Offer.objects.filter(**simplejson.loads(m.queryset_filter_kwargs)).order_by('-pk')
		m.latest_object_pk = queryset[:1][0].pk if queryset.count() > 0 else None
		#m.latest_object_content_type = ContentType.objects.get_for_model(Offer)
		m.last_run = timezone.now()
		if commit:
			m.save()
		return m
	

class  AlertOfferCreateForm(AlertOfferUpdateForm):
	""" Used to create alerts for offers - derived from offer update but need to specify a few defaults prior to save """
	class Meta:
		model =  Alert
		fields = list(AlertOfferUpdateForm.Meta.fields) + ['latest_object_content_type'] # show these fields from model
	
	latest_object_content_type = forms.ModelChoiceField(queryset=ContentType.objects.all(), 
													initial=ContentType.objects.get_for_model(Offer), 
													widget=widgets.HiddenInput(attrs={'readonly': 'readonly'}))
	
	def __init__(self, user, *args, **kwargs):
		self.user = user
		super(AlertOfferCreateForm, self).__init__(*args, **kwargs)
		
	def clean_latest_object_content_type(self):
		# scrub the POST and always return the desired value
		return ContentType.objects.get_for_model(Offer)
	
	def save(self, commit=True):
		m = super(AlertOfferCreateForm, self).save(commit = False)
		# add the content type and object id 
		#raise Exception(simplejson.loads(m.queryset_filter_kwargs))
		#queryset = Offer.objects.filter(**simplejson.loads(m.queryset_filter_kwargs)).order_by('-pk')
		
		m.user = self.user # we only need the user as we do the other defaults already
		
		#m.latest_object_pk = queryset[:1][0].pk if queryset.count() > 0 else None
		#m.latest_object_content_type = ContentType.objects.get_for_model(Offer)
		#m.last_run = timezone.now()
		if commit:
			m.save()
		return m
	
	
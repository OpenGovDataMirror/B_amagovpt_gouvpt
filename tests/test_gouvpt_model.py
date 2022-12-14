# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import pytest

from uuid import uuid4, UUID
from datetime import date, datetime, timedelta

from mongoengine.errors import ValidationError
from mongoengine.fields import BaseField

from udata.settings import Defaults
from udata.models import db, Dataset, validate_config, build_test_config
from udata.errors import ConfigError
from udata.tests.helpers import assert_json_equal

pytestmark = [
    pytest.mark.usefixtures('clean_db')
]


class UUIDTester(db.Document):
    uuid = db.AutoUUIDField()


class UUIDAsIdTester(db.Document):
    id = db.AutoUUIDField(primary_key=True)


class SlugTester(db.Document):
    title = db.StringField()
    slug = db.SlugField(populate_from='title', max_length=1000)
    meta = {
        'allow_inheritance': True,
    }


class SlugUpdateTester(db.Document):
    title = db.StringField()
    slug = db.SlugField(populate_from='title', update=True)


class DateTester(db.Document):
    a_date = db.DateField()


class DateTesterWithDefault(db.Document):
    a_date = db.DateField(default=date.today)


class InheritedSlugTester(SlugTester):
    other = db.StringField()


class DatetimedTester(db.Datetimed, db.Document):
    name = db.StringField()


class URLTester(db.Document):
    url = db.URLField()


class PrivateURLTester(db.Document):
    url = db.URLField(private=True)


class AutoUUIDFieldTest:
    def test_auto_populate(self):
        '''AutoUUIDField should populate itself if not set'''
        obj = UUIDTester()
        assert obj.uuid is not None
        assert isinstance(obj.uuid, UUID)

    def test_do_not_overwrite(self):
        '''AutoUUIDField shouldn't populate itself if a value is already set'''
        uuid = uuid4()
        obj = UUIDTester(uuid=uuid)
        assert obj.uuid == uuid

    def test_as_primary_key(self):
        obj = UUIDAsIdTester()
        assert obj.id is not None
        assert isinstance(obj.id, UUID)
        assert obj.pk == obj.id

    def test_query_as_uuid(self):
        obj = UUIDAsIdTester.objects.create()
        assert isinstance(obj.id, UUID)
        assert UUIDAsIdTester.objects.get(id=obj.id) == obj

    def test_query_as_text(self):
        obj = UUIDAsIdTester.objects.create()
        assert UUIDAsIdTester.objects.get(id=str(obj.id)) == obj

    def test_always_an_uuid(self):
        obj = UUIDTester(uuid=str(uuid4()))
        assert isinstance(obj.uuid, UUID)


class SlugFieldTest:
    def test_validate(self):
        '''SlugField should validate if not set'''
        obj = SlugTester(title="A Title")
        assert obj.slug is None
        obj.validate()

    def test_populate(self):
        '''SlugField should populate itself on save if not set'''
        obj = SlugTester(title="A Title")
        assert obj.slug is None
        obj.save()
        assert obj.slug == 'a-title'

    def test_populate_next(self):
        '''SlugField should not keep other fields value'''
        obj = SlugTester.objects.create(title="A Title")
        obj.slug = 'fake'
        obj = SlugTester.objects.create(title="Another title")
        assert obj.slug == 'another-title'

    def test_populate_parallel(self):
        '''SlugField should not take other instance values'''
        obj1 = SlugTester.objects.create(title="A Title")
        obj = SlugTester.objects.create(title="Another title")
        obj1.slug = 'fake'
        assert obj.slug == 'another-title'

    def test_no_populate(self):
        '''SlugField should not populate itself if a value is set'''
        obj = SlugTester(title='A Title', slug='a-slug')
        obj.save()
        assert obj.slug == 'a-slug'

    def test_populate_update(self):
        '''SlugField should populate itself on save and update'''
        obj = SlugUpdateTester(title="A Title")
        obj.save()
        assert obj.slug == 'a-title'
        obj.title = 'Title'
        obj.save()
        assert obj.slug == 'title'

    def test_no_populate_update(self):
        '''SlugField should not populate itself if a value is set'''
        obj = SlugUpdateTester(title="A Title")
        obj.save()
        assert obj.slug == 'a-title'
        obj.title = 'Title'
        obj.slug = 'other'
        obj.save()
        assert obj.slug == 'other'

    def test_unchanged(self):
        '''SlugField should not change on save if not needed'''
        obj = SlugTester(title="A Title")
        assert obj.slug is None
        obj.save()
        assert obj.slug == 'a-title'
        obj.save()
        assert obj.slug == 'a-title'

    def test_changed_no_update(self):
        '''SlugField should not update slug if update=False'''
        obj = SlugTester(title="A Title")
        obj.save()
        assert obj.slug == 'a-title'
        obj.title = 'Title'
        obj.save()
        assert obj.slug == 'a-title'

    def test_manually_set(self):
        '''SlugField can be manually set'''
        obj = SlugTester(title='A title', slug='a-slug')
        assert obj.slug == 'a-slug'
        obj.save()
        assert obj.slug == 'a-slug'

    def test_work_accross_inheritance(self):
        '''SlugField should ensure uniqueness accross inheritance'''
        obj = SlugTester.objects.create(title='title')
        inherited = InheritedSlugTester.objects.create(title='title')
        assert obj.slug != inherited.slug

    def test_crop(self):
        '''SlugField should truncate itself on save if not set'''
        obj = SlugTester(title='x' * (SlugTester.slug.max_length + 1))
        obj.save()
        assert len(obj.title) == SlugTester.slug.max_length + 1
        assert len(obj.slug) == SlugTester.slug.max_length

    def test_multiple_spaces(self):
        field = db.SlugField()
        assert field.slugify('a  b') == 'a-b'

    def test_lower_case_default(self):
        field = db.SlugField()
        assert field.slugify('ABC') == 'abc'

    def test_lower_case_false(self):
        field = db.SlugField(lower_case=False)
        assert field.slugify('AbC') == 'AbC'

    def test_custom_separator(self):
        field = db.SlugField(separator='+')
        assert field.slugify('a b') == 'a+b'

    def test_is_stripped(self):
        field = db.SlugField()
        assert field.slugify('  ab  ') == 'ab'

    def test_special_chars_are_normalized(self):
        field = db.SlugField()
        assert field.slugify('??-???-??') == 'a-eur-u'


class DateFieldTest:
    def test_none_if_empty_and_not_required(self):
        obj = DateTester()
        assert obj.a_date is None
        obj.save()
        obj.reload()
        assert obj.a_date is None

    def test_default(self):
        today = date.today()
        obj = DateTesterWithDefault()
        assert obj.a_date == today
        obj.save()
        obj.reload()
        assert obj.a_date == today

    def test_date(self):
        the_date = date(1984, 6, 6)
        obj = DateTester(a_date=the_date)
        assert obj.a_date == the_date
        obj.save()
        obj.reload()
        assert obj.a_date == the_date

    def test_not_valid(self):
        obj = DateTester(a_date='invalid')
        with pytest.raises(ValidationError):
            obj.save()


class URLFieldTest:
    def test_none_if_empty_and_not_required(self):
        obj = URLTester()
        assert obj.url is None
        obj.save()
        obj.reload()
        assert obj.url is None

    def test_not_valid(self):
        obj = URLTester(url='invalid')
        with pytest.raises(ValidationError):
            obj.save()

    def test_strip_spaces(self):
        url = '  https://www.somewhere.com/with/spaces/   '
        obj = URLTester(url=url)
        obj.save().reload()
        assert obj.url == url.strip()

    def test_handle_unicode(self):
        url = 'https://www.somewh??re.com/with/acc??nts/'
        obj = URLTester(url=url)
        obj.save().reload()
        assert obj.url == url

    def test_public_private(self):
        url = 'http://10.10.0.2/path/'
        PrivateURLTester(url=url).save()
        with pytest.raises(ValidationError):
            URLTester(url=url).save()


class DatetimedTest:
    def test_class(self):
        assert isinstance(DatetimedTester.created_at, db.DateTimeField)
        assert isinstance(DatetimedTester.last_modified, db.DateTimeField)

    def test_new_instance(self):
        now = datetime.now()
        datetimed = DatetimedTester()

        assert now <= datetimed.created_at <= datetime.now()
        assert now <= datetimed.last_modified <= datetime.now()

    def test_save_new_instance(self):
        now = datetime.now()
        datetimed = DatetimedTester.objects.create()

        assert now <= datetimed.created_at <= datetime.now()
        assert now <= datetimed.last_modified <= datetime.now()

    def test_save_last_modified_instance(self):
        now = datetime.now()
        earlier = now - timedelta(days=1)
        datetimed = DatetimedTester.objects.create(
            created_at=earlier, last_modified=earlier)

        datetimed.save()

        assert datetimed.created_at == earlier
        assert now <= datetimed.last_modified <= datetime.now()


class ExtrasFieldTest:
    def test_default_validate_primitive_type(self):
        class Tester(db.Document):
            extras = db.ExtrasField()

        now = datetime.now()
        today = date.today()

        tester = Tester(extras={
            'string': 'string',
            'integer': 5,
            'float': 5.5,
            'datetime': now,
            'date': today,
            'bool': True
        })
        tester.validate()

    def test_default_dont_validate_complex_types(self):
        class Tester(db.Document):
            extras = db.ExtrasField()

        tester = Tester(extras={'dict': {}})

        with pytest.raises(ValidationError):
            tester.validate()

    def test_can_only_register_db_type(self):
        class Tester(db.Document):
            extras = db.ExtrasField()

        with pytest.raises(TypeError):
            Tester.extras.register('test', datetime)

    @pytest.mark.parametrize('dbtype,value', [
        (db.IntField, 42),
        (db.FloatField, 0.42),
        (db.BooleanField, True),
        (db.DateTimeField, datetime.now()),
        (db.DateField, date.today()),
    ])
    def test_validate_registered_db_type(self, dbtype, value):
        class Tester(db.Document):
            extras = db.ExtrasField()

        Tester.extras.register('test', dbtype)

        Tester(extras={'test': value}).validate()

    @pytest.mark.parametrize('dbtype,value', [
        (db.IntField, datetime.now()),
        (db.FloatField, datetime.now()),
        (db.BooleanField, 42),
        (db.DateTimeField, 42),
        (db.DateField, 42),
    ])
    def test_fail_to_validate_wrong_type(self, dbtype, value):
        class Tester(db.Document):
            extras = db.ExtrasField()

        Tester.extras.register('test', dbtype)

        with pytest.raises(db.ValidationError):
            Tester(extras={'test': value}).validate()

    def test_validate_custom_type(self):
        class Tester(db.Document):
            extras = db.ExtrasField()

        @Tester.extras('test')
        class Custom(BaseField):
            def validate(self, value):
                if not isinstance(value, dict):
                    raise db.ValidationError('Should be a dict instance')

        tester = Tester(extras={'test': {}})
        tester.validate()

    def test_validate_registered_type_embedded_document(self):
        class Tester(db.Document):
            extras = db.ExtrasField()

        @Tester.extras('test')
        class EmbeddedExtra(db.EmbeddedDocument):
            name = db.StringField(required=True)

        tester = Tester(extras={'test': {}})
        with pytest.raises(ValidationError):
            tester.validate()

        tester.extras['test'] = {'name': 'test'}
        tester.validate()

        tester.extras['test'] = EmbeddedExtra(name='test')
        tester.validate()

    def test_is_json_serializable(self):
        class Tester(db.Document):
            extras = db.ExtrasField()

        @Tester.extras('embedded')
        class EmbeddedExtra(db.EmbeddedDocument):
            name = db.StringField(required=True)

        tester = Tester(extras={
            'test': {'key': 'value'},
            'embedded': EmbeddedExtra(name='An embedded field'),
            'string': 'a value',
            'integer': 5,
            'float': 5.5,
        })

        assert_json_equal(tester.extras, {
            'test': {'key': 'value'},
            'embedded': {'name': 'An embedded field'},
            'string': 'a value',
            'integer': 5,
            'float': 5.5,
        })


class ModelResolutionTest:
    def test_resolve_exact_match(self):
        assert db.resolve_model('Dataset') == Dataset

    def test_resolve_from_dict(self):
        assert db.resolve_model({'class': 'Dataset'}) == Dataset

    def test_raise_if_not_found(self):
        with pytest.raises(ValueError):
            db.resolve_model('NotFound')

    def test_raise_if_not_a_document(self):
        with pytest.raises(ValueError):
            db.resolve_model('UDataMongoEngine')

    def test_raise_if_none(self):
        with pytest.raises(ValueError):
            db.resolve_model(None)

    def test_raise_if_missing_class_entry(self):
        with pytest.raises(ValueError):
            db.resolve_model({'field': 'value'})


class MongoConfigTest:
    def test_validate_default_value(self):
        validate_config({'MONGODB_HOST': Defaults.MONGODB_HOST})

    def test_validate_with_auth(self):
        validate_config({'MONGODB_HOST': 'mongodb://userid:password@somewhere.com:1234/mydb'})

    def test_raise_exception_on_host_only(self):
        with pytest.raises(ConfigError):
            validate_config({'MONGODB_HOST': 'somehost'})

    def test_raise_exception_on_missing_db(self):
        with pytest.raises(ConfigError):
            validate_config({'MONGODB_HOST': 'mongodb://somewhere.com:1234'})
        with pytest.raises(ConfigError):
            validate_config({'MONGODB_HOST': 'mongodb://somewhere.com:1234/'})

    def test_warn_on_deprecated_db_port(self):
        with pytest.deprecated_call():
            validate_config({'MONGODB_HOST': Defaults.MONGODB_HOST,
                             'MONGODB_PORT': 1234})
        with pytest.deprecated_call():
            validate_config({'MONGODB_HOST': Defaults.MONGODB_HOST,
                             'MONGODB_DB': 'udata'})

    def test_build_test_config_with_MONGODB_HOST_TEST(self):
        test_url = 'mongodb://somewhere.com:1234/test'
        config = {'MONGODB_HOST_TEST': test_url}
        build_test_config(config)
        assert 'MONGODB_HOST' in config
        assert config['MONGODB_HOST'] == test_url

    def test_build_test_config_without_MONGODB_HOST_TEST(self):
        config = {'MONGODB_HOST': Defaults.MONGODB_HOST}
        expected = '{0}-test'.format(Defaults.MONGODB_HOST)
        build_test_config(config)
        assert config['MONGODB_HOST'] == expected

    def test_build_test_config_should_validate(self):
        with pytest.raises(ConfigError):
            test_url = 'mongodb://somewhere.com:1234'
            config = {'MONGODB_HOST_TEST': test_url}
            build_test_config(config)

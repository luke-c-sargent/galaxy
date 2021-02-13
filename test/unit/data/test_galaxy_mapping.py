import collections
import os
import unittest
import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy_utils import create_database

import galaxy.datatypes.registry
import galaxy.model
import galaxy.model.mapping as mapping
from galaxy.model.security import GalaxyRBACAgent

datatypes_registry = galaxy.datatypes.registry.Registry()
datatypes_registry.load_datatypes()
galaxy.model.set_datatypes_registry(datatypes_registry)

DB_URI = "sqlite:///:memory:"
# docker run -e POSTGRES_USER=galaxy -p 5432:5432 -d postgres
# GALAXY_TEST_UNIT_MAPPING_URI_POSTGRES_BASE='postgresql://galaxy@localhost:5432/' pytest test/unit/data/test_galaxy_mapping.py
skip_if_not_postgres_base = pytest.mark.skipif(
    not os.environ.get('GALAXY_TEST_UNIT_MAPPING_URI_POSTGRES_BASE'),
    reason="GALAXY_TEST_UNIT_MAPPING_URI_POSTGRES_BASE not set"
)


class BaseModelTestCase(unittest.TestCase):

    @classmethod
    def _db_uri(cls):
        return DB_URI

    @classmethod
    def setUpClass(cls):
        # Start the database and connect the mapping
        cls.model = mapping.init("/tmp", cls._db_uri(), create_tables=True, object_store=MockObjectStore())
        assert cls.model.engine is not None

    @classmethod
    def query(cls, type):
        return cls.model.session.query(type)

    @classmethod
    def persist(cls, *args, **kwargs):
        session = cls.session()
        flush = kwargs.get('flush', True)
        for arg in args:
            session.add(arg)
            if flush:
                session.flush()
        if kwargs.get('expunge', not flush):
            cls.expunge()
        return arg  # Return last or only arg.

    @classmethod
    def session(cls):
        return cls.model.session

    @classmethod
    def expunge(cls):
        cls.model.session.flush()
        cls.model.session.expunge_all()


class MappingTests(BaseModelTestCase):

    def test_annotations(self):
        model = self.model

        u = model.User(email="annotator@example.com", password="password")
        self.persist(u)

        def persist_and_check_annotation(annotation_class, **kwds):
            annotated_association = annotation_class()
            annotated_association.annotation = "Test Annotation"
            annotated_association.user = u
            for key, value in kwds.items():
                setattr(annotated_association, key, value)
            self.persist(annotated_association)
            self.expunge()
            stored_annotation = self.query(annotation_class).all()[0]
            assert stored_annotation.annotation == "Test Annotation"
            assert stored_annotation.user.email == "annotator@example.com"

        sw = model.StoredWorkflow()
        sw.user = u
        self.persist(sw)
        persist_and_check_annotation(model.StoredWorkflowAnnotationAssociation, stored_workflow=sw)

        workflow = model.Workflow()
        workflow.stored_workflow = sw
        self.persist(workflow)

        ws = model.WorkflowStep()
        ws.workflow = workflow
        self.persist(ws)
        persist_and_check_annotation(model.WorkflowStepAnnotationAssociation, workflow_step=ws)

        h = model.History(name="History for Annotation", user=u)
        self.persist(h)
        persist_and_check_annotation(model.HistoryAnnotationAssociation, history=h)

        d1 = model.HistoryDatasetAssociation(extension="txt", history=h, create_dataset=True, sa_session=model.session)
        self.persist(d1)
        persist_and_check_annotation(model.HistoryDatasetAssociationAnnotationAssociation, hda=d1)

        page = model.Page()
        page.user = u
        self.persist(page)
        persist_and_check_annotation(model.PageAnnotationAssociation, page=page)

        visualization = model.Visualization()
        visualization.user = u
        self.persist(visualization)
        persist_and_check_annotation(model.VisualizationAnnotationAssociation, visualization=visualization)

        dataset_collection = model.DatasetCollection(collection_type="paired")
        history_dataset_collection = model.HistoryDatasetCollectionAssociation(collection=dataset_collection)
        self.persist(history_dataset_collection)
        persist_and_check_annotation(model.HistoryDatasetCollectionAssociationAnnotationAssociation, history_dataset_collection=history_dataset_collection)

        library_dataset_collection = model.LibraryDatasetCollectionAssociation(collection=dataset_collection)
        self.persist(library_dataset_collection)
        persist_and_check_annotation(model.LibraryDatasetCollectionAnnotationAssociation, library_dataset_collection=library_dataset_collection)

    def test_ratings(self):
        model = self.model

        u = model.User(email="rater@example.com", password="password")
        self.persist(u)

        def persist_and_check_rating(rating_class, **kwds):
            rating_association = rating_class()
            rating_association.rating = 5
            rating_association.user = u
            for key, value in kwds.items():
                setattr(rating_association, key, value)
            self.persist(rating_association)
            self.expunge()
            stored_annotation = self.query(rating_class).all()[0]
            assert stored_annotation.rating == 5
            assert stored_annotation.user.email == "rater@example.com"

        sw = model.StoredWorkflow()
        sw.user = u
        self.persist(sw)
        persist_and_check_rating(model.StoredWorkflowRatingAssociation, stored_workflow=sw)

        h = model.History(name="History for Rating", user=u)
        self.persist(h)
        persist_and_check_rating(model.HistoryRatingAssociation, history=h)

        d1 = model.HistoryDatasetAssociation(extension="txt", history=h, create_dataset=True, sa_session=model.session)
        self.persist(d1)
        persist_and_check_rating(model.HistoryDatasetAssociationRatingAssociation, hda=d1)

        page = model.Page()
        page.user = u
        self.persist(page)
        persist_and_check_rating(model.PageRatingAssociation, page=page)

        visualization = model.Visualization()
        visualization.user = u
        self.persist(visualization)
        persist_and_check_rating(model.VisualizationRatingAssociation, visualization=visualization)

        dataset_collection = model.DatasetCollection(collection_type="paired")
        history_dataset_collection = model.HistoryDatasetCollectionAssociation(collection=dataset_collection)
        self.persist(history_dataset_collection)
        persist_and_check_rating(model.HistoryDatasetCollectionRatingAssociation, history_dataset_collection=history_dataset_collection)

        library_dataset_collection = model.LibraryDatasetCollectionAssociation(collection=dataset_collection)
        self.persist(library_dataset_collection)
        persist_and_check_rating(model.LibraryDatasetCollectionRatingAssociation, library_dataset_collection=library_dataset_collection)

    def test_display_name(self):

        def assert_display_name_converts_to_unicode(item, name):
            assert isinstance(item.get_display_name(), str)
            assert item.get_display_name() == name

        ldda = self.model.LibraryDatasetDatasetAssociation(name='ldda_name')
        assert_display_name_converts_to_unicode(ldda, 'ldda_name')

        hda = self.model.HistoryDatasetAssociation(name='hda_name')
        assert_display_name_converts_to_unicode(hda, 'hda_name')

        history = self.model.History(name='history_name')
        assert_display_name_converts_to_unicode(history, 'history_name')

        library = self.model.Library(name='library_name')
        assert_display_name_converts_to_unicode(library, 'library_name')

        library_folder = self.model.LibraryFolder(name='library_folder')
        assert_display_name_converts_to_unicode(library_folder, 'library_folder')

        history = self.model.History(
            name='Hello₩◎ґʟⅾ'
        )

        assert isinstance(history.name, str)
        assert isinstance(history.get_display_name(), str)
        assert history.get_display_name() == 'Hello₩◎ґʟⅾ'

    def test_hda_to_library_dataset_dataset_association(self):
        u = self.model.User(email="mary@example.com", password="password")
        hda = self.model.HistoryDatasetAssociation(name='hda_name')
        self.persist(hda)
        trans = collections.namedtuple('trans', 'user')
        target_folder = self.model.LibraryFolder(name='library_folder')
        ldda = hda.to_library_dataset_dataset_association(
            trans=trans(user=u),
            target_folder=target_folder,
        )
        assert target_folder.item_count == 1
        assert ldda.id
        assert ldda.library_dataset.id
        assert ldda.library_dataset_id
        assert ldda.library_dataset.library_dataset_dataset_association
        assert ldda.library_dataset.library_dataset_dataset_association_id
        library_dataset_id = ldda.library_dataset_id
        replace_dataset = ldda.library_dataset
        new_ldda = hda.to_library_dataset_dataset_association(
            trans=trans(user=u),
            target_folder=target_folder,
            replace_dataset=replace_dataset
        )
        assert new_ldda.id != ldda.id
        assert new_ldda.library_dataset_id == library_dataset_id
        assert new_ldda.library_dataset.library_dataset_dataset_association_id == new_ldda.id
        assert len(new_ldda.library_dataset.expired_datasets) == 1
        assert new_ldda.library_dataset.expired_datasets[0] == ldda
        assert target_folder.item_count == 1

    def test_tags(self):
        model = self.model

        my_tag = model.Tag(name="Test Tag")
        u = model.User(email="tagger@example.com", password="password")
        self.persist(my_tag, u)

        def tag_and_test(taggable_object, tag_association_class, backref_name):
            assert len(getattr(self.query(model.Tag).filter(model.Tag.name == "Test Tag").all()[0], backref_name)) == 0

            tag_association = tag_association_class()
            tag_association.tag = my_tag
            taggable_object.tags = [tag_association]
            self.persist(tag_association, taggable_object)

            assert len(getattr(self.query(model.Tag).filter(model.Tag.name == "Test Tag").all()[0], backref_name)) == 1

        sw = model.StoredWorkflow()
        sw.user = u
        tag_and_test(sw, model.StoredWorkflowTagAssociation, "tagged_workflows")

        h = model.History(name="History for Tagging", user=u)
        tag_and_test(h, model.HistoryTagAssociation, "tagged_histories")

        d1 = model.HistoryDatasetAssociation(extension="txt", history=h, create_dataset=True, sa_session=model.session)
        tag_and_test(d1, model.HistoryDatasetAssociationTagAssociation, "tagged_history_dataset_associations")

        page = model.Page()
        page.user = u
        tag_and_test(page, model.PageTagAssociation, "tagged_pages")

        visualization = model.Visualization()
        visualization.user = u
        tag_and_test(visualization, model.VisualizationTagAssociation, "tagged_visualizations")

        dataset_collection = model.DatasetCollection(collection_type="paired")
        history_dataset_collection = model.HistoryDatasetCollectionAssociation(collection=dataset_collection)
        tag_and_test(history_dataset_collection, model.HistoryDatasetCollectionTagAssociation, "tagged_history_dataset_collections")

        library_dataset_collection = model.LibraryDatasetCollectionAssociation(collection=dataset_collection)
        tag_and_test(library_dataset_collection, model.LibraryDatasetCollectionTagAssociation, "tagged_library_dataset_collections")

    def test_collections_in_histories(self):
        model = self.model

        u = model.User(email="mary@example.com", password="password")
        h1 = model.History(name="History 1", user=u)
        d1 = model.HistoryDatasetAssociation(extension="txt", history=h1, create_dataset=True, sa_session=model.session)
        d2 = model.HistoryDatasetAssociation(extension="txt", history=h1, create_dataset=True, sa_session=model.session)

        c1 = model.DatasetCollection(collection_type="pair")
        hc1 = model.HistoryDatasetCollectionAssociation(history=h1, collection=c1, name="HistoryCollectionTest1")

        dce1 = model.DatasetCollectionElement(collection=c1, element=d1, element_identifier="left")
        dce2 = model.DatasetCollectionElement(collection=c1, element=d2, element_identifier="right")

        self.persist(u, h1, d1, d2, c1, hc1, dce1, dce2)

        loaded_dataset_collection = self.query(model.HistoryDatasetCollectionAssociation).filter(model.HistoryDatasetCollectionAssociation.name == "HistoryCollectionTest1").first().collection
        self.assertEqual(len(loaded_dataset_collection.elements), 2)
        assert loaded_dataset_collection.collection_type == "pair"
        assert loaded_dataset_collection["left"] == dce1
        assert loaded_dataset_collection["right"] == dce2

    def test_collections_in_library_folders(self):
        model = self.model

        u = model.User(email="mary2@example.com", password="password")
        lf = model.LibraryFolder(name="RootFolder")
        library = model.Library(name="Library1", root_folder=lf)
        ld1 = model.LibraryDataset()
        ld2 = model.LibraryDataset()

        ldda1 = model.LibraryDatasetDatasetAssociation(extension="txt", library_dataset=ld1)
        ldda2 = model.LibraryDatasetDatasetAssociation(extension="txt", library_dataset=ld1)

        c1 = model.DatasetCollection(collection_type="pair")
        dce1 = model.DatasetCollectionElement(collection=c1, element=ldda1)
        dce2 = model.DatasetCollectionElement(collection=c1, element=ldda2)
        self.persist(u, library, lf, ld1, ld2, c1, ldda1, ldda2, dce1, dce2)

        # TODO:
        # loaded_dataset_collection = self.query( model.DatasetCollection ).filter( model.DatasetCollection.name == "LibraryCollectionTest1" ).first()
        # self.assertEqual(len(loaded_dataset_collection.datasets), 2)
        # assert loaded_dataset_collection.collection_type == "pair"

    def test_default_disk_usage(self):
        model = self.model

        u = model.User(email="disk_default@test.com", password="password")
        self.persist(u)
        u.adjust_total_disk_usage(1)
        u_id = u.id
        self.expunge()
        user_reload = model.session.query(model.User).get(u_id)
        assert user_reload.disk_usage == 1

    def test_basic(self):
        model = self.model

        original_user_count = len(model.session.query(model.User).all())

        # Make some changes and commit them
        u = model.User(email="james@foo.bar.baz", password="password")
        # gs = model.GalaxySession()
        h1 = model.History(name="History 1", user=u)
        # h1.queries.append( model.Query( "h1->q1" ) )
        # h1.queries.append( model.Query( "h1->q2" ) )
        h2 = model.History(name=("H" * 1024))
        self.persist(u, h1, h2)
        # q1 = model.Query( "h2->q1" )
        metadata = dict(chromCol=1, startCol=2, endCol=3)
        d1 = model.HistoryDatasetAssociation(extension="interval", metadata=metadata, history=h2, create_dataset=True, sa_session=model.session)
        # h2.queries.append( q1 )
        # h2.queries.append( model.Query( "h2->q2" ) )
        self.persist(d1)

        # Check
        users = model.session.query(model.User).all()
        assert len(users) == original_user_count + 1
        user = [user for user in users if user.email == "james@foo.bar.baz"][0]
        assert user.email == "james@foo.bar.baz"
        assert user.password == "password"
        assert len(user.histories) == 1
        assert user.histories[0].name == "History 1"
        hists = model.session.query(model.History).all()
        hist0 = [history for history in hists if history.name == "History 1"][0]
        hist1 = [history for history in hists if history.name == "H" * 255][0]
        assert hist0.name == "History 1"
        assert hist1.name == ("H" * 255)
        assert hist0.user == user
        assert hist1.user is None
        assert hist1.datasets[0].metadata.chromCol == 1
        # The filename test has moved to objectstore
        # id = hist1.datasets[0].id
        # assert hist1.datasets[0].file_name == os.path.join( "/tmp", *directory_hash_id( id ) ) + ( "/dataset_%d.dat" % id )
        # Do an update and check
        hist1.name = "History 2b"
        self.expunge()
        hists = model.session.query(model.History).all()
        hist0 = [history for history in hists if history.name == "History 1"][0]
        hist1 = [history for history in hists if history.name == "History 2b"][0]
        assert hist0.name == "History 1"
        assert hist1.name == "History 2b"
        # gvk TODO need to ad test for GalaxySessions, but not yet sure what they should look like.

    def test_metadata_spec(self):
        metadata = dict(chromCol=1, startCol=2, endCol=3)
        d = self.model.HistoryDatasetAssociation(extension="interval", metadata=metadata, sa_session=self.model.session)
        assert d.metadata.chromCol == 1
        assert d.metadata.anyAttribute is None

    def test_jobs(self):
        model = self.model
        u = model.User(email="jobtest@foo.bar.baz", password="password")
        job = model.Job()
        job.user = u
        job.tool_id = "cat1"

        self.persist(u, job)

        loaded_job = model.session.query(model.Job).filter(model.Job.user == u).first()
        assert loaded_job.tool_id == "cat1"

    def test_job_metrics(self):
        model = self.model
        u = model.User(email="jobtest@foo.bar.baz", password="password")
        job = model.Job()
        job.user = u
        job.tool_id = "cat1"

        job.add_metric("gx", "galaxy_slots", 5)
        job.add_metric("system", "system_name", "localhost")

        self.persist(u, job)

        task = model.Task(job=job, working_directory="/tmp", prepare_files_cmd="split.sh")
        task.add_metric("gx", "galaxy_slots", 5)
        task.add_metric("system", "system_name", "localhost")

        big_value = ":".join("%d" % i for i in range(2000))
        task.add_metric("env", "BIG_PATH", big_value)
        self.persist(task)
        # Ensure big values truncated
        assert len(task.text_metrics[1].metric_value) <= 1023

    def test_tasks(self):
        model = self.model
        u = model.User(email="jobtest@foo.bar.baz", password="password")
        job = model.Job()
        task = model.Task(job=job, working_directory="/tmp", prepare_files_cmd="split.sh")
        job.user = u
        self.persist(u, job, task)

        loaded_task = model.session.query(model.Task).filter(model.Task.job == job).first()
        assert loaded_task.prepare_input_files_cmd == "split.sh"

    def test_history_contents(self):
        model = self.model
        u = model.User(email="contents@foo.bar.baz", password="password")
        # gs = model.GalaxySession()
        h1 = model.History(name="HistoryContentsHistory1", user=u)

        self.persist(u, h1, expunge=False)

        d1 = self.new_hda(h1, name="1")
        d2 = self.new_hda(h1, name="2", visible=False)
        d3 = self.new_hda(h1, name="3", deleted=True)
        d4 = self.new_hda(h1, name="4", visible=False, deleted=True)

        self.session().flush()

        def contents_iter_names(**kwds):
            history = model.context.query(model.History).filter(
                model.History.name == "HistoryContentsHistory1"
            ).first()
            return list(map(lambda hda: hda.name, history.contents_iter(**kwds)))

        self.assertEqual(contents_iter_names(), ["1", "2", "3", "4"])
        assert contents_iter_names(deleted=False) == ["1", "2"]
        assert contents_iter_names(visible=True) == ["1", "3"]
        assert contents_iter_names(visible=False) == ["2", "4"]
        assert contents_iter_names(deleted=True, visible=False) == ["4"]

        assert contents_iter_names(ids=[d1.id, d2.id, d3.id, d4.id]) == ["1", "2", "3", "4"]
        assert contents_iter_names(ids=[d1.id, d2.id, d3.id, d4.id], max_in_filter_length=1) == ["1", "2", "3", "4"]

        assert contents_iter_names(ids=[d1.id, d3.id]) == ["1", "3"]

    def _non_empty_flush(self):
        model = self.model
        lf = model.LibraryFolder(name="RootFolder")
        session = self.session()
        session.add(lf)
        session.flush()

    def test_flush_refreshes(self):
        # Normally I don't believe in unit testing library code, but the behaviors around attribute
        # states and flushing in SQL Alchemy is very subtle and it is good to have a executable
        # reference for how it behaves in the context of Galaxy objects.
        model = self.model
        user = model.User(
            email="testworkflows@bx.psu.edu",
            password="password"
        )
        galaxy_session = model.GalaxySession()
        galaxy_session_other = model.GalaxySession()
        galaxy_session.user = user
        galaxy_session_other.user = user
        self.persist(user, galaxy_session_other, galaxy_session)
        galaxy_session_id = galaxy_session.id

        self.expunge()
        session = self.session()
        galaxy_model_object = self.query(model.GalaxySession).get(galaxy_session_id)
        expected_id = galaxy_model_object.id

        # id loaded as part of the object query, could be any non-deferred attribute.
        assert 'id' not in inspect(galaxy_model_object).unloaded

        # Perform an empty flush, verify empty flush doesn't reload all attributes.
        session.flush()
        assert 'id' not in inspect(galaxy_model_object).unloaded

        # However, flushing anything non-empty - even unrelated object will invalidate
        # the session ID.
        self._non_empty_flush()
        assert 'id' in inspect(galaxy_model_object).unloaded

        # Fetch the ID loads the value from the database
        assert expected_id == galaxy_model_object.id
        assert 'id' not in inspect(galaxy_model_object).unloaded

        # Using cached_id instead does not exhibit this behavior.
        self._non_empty_flush()
        assert expected_id == galaxy.model.cached_id(galaxy_model_object)
        assert 'id' in inspect(galaxy_model_object).unloaded

        # Keeping the following failed experiments here for future reference,
        # I probed the internals of the attribute tracking and couldn't find an
        # alternative, generalized way to get the previously loaded value for unloaded
        # attributes.
        # print(galaxy_model_object._sa_instance_state.attrs.id)
        # print(dir(galaxy_model_object._sa_instance_state.attrs.id))
        # print(galaxy_model_object._sa_instance_state.attrs.id.loaded_value)
        # print(galaxy_model_object._sa_instance_state.attrs.id.state)
        # print(galaxy_model_object._sa_instance_state.attrs.id.load_history())
        # print(dir(galaxy_model_object._sa_instance_state.attrs.id.load_history()))
        # print(galaxy_model_object._sa_instance_state.identity)
        # print(dir(galaxy_model_object._sa_instance_state))
        # print(galaxy_model_object._sa_instance_state.expired_attributes)
        # print(galaxy_model_object._sa_instance_state.expired)
        # print(galaxy_model_object._sa_instance_state._instance_dict().keys())
        # print(dir(galaxy_model_object._sa_instance_state._instance_dict))
        # assert False

        # Verify cached_id works even immediately after an initial flush, prevents a second SELECT
        # query that would be executed if object.id was used.
        galaxy_model_object_new = model.GalaxySession()
        session.add(galaxy_model_object_new)
        session.flush()
        assert galaxy.model.cached_id(galaxy_model_object_new)
        assert 'id' in inspect(galaxy_model_object_new).unloaded

        # Verify a targeted flush prevent expiring unrelated objects.
        galaxy_model_object_new.id
        assert 'id' not in inspect(galaxy_model_object_new).unloaded
        session.flush(model.GalaxySession())
        assert 'id' not in inspect(galaxy_model_object_new).unloaded

    def test_workflows(self):
        model = self.model
        user = model.User(
            email="testworkflows@bx.psu.edu",
            password="password"
        )

        def workflow_from_steps(steps):
            stored_workflow = model.StoredWorkflow()
            stored_workflow.user = user
            workflow = model.Workflow()
            workflow.steps = steps
            workflow.stored_workflow = stored_workflow
            return workflow

        child_workflow = workflow_from_steps([])
        self.persist(child_workflow)

        workflow_step_1 = model.WorkflowStep()
        workflow_step_1.order_index = 0
        workflow_step_1.type = "data_input"
        workflow_step_2 = model.WorkflowStep()
        workflow_step_2.order_index = 1
        workflow_step_2.type = "subworkflow"
        workflow_step_2.subworkflow = child_workflow

        workflow_step_1.get_or_add_input("moo1")
        workflow_step_1.get_or_add_input("moo2")
        workflow_step_2.get_or_add_input("moo")
        workflow_step_1.add_connection("foo", "cow", workflow_step_2)

        workflow = workflow_from_steps([workflow_step_1, workflow_step_2])
        self.persist(workflow)
        workflow_id = workflow.id

        annotation = model.WorkflowStepAnnotationAssociation()
        annotation.annotation = "Test Step Annotation"
        annotation.user = user
        annotation.workflow_step = workflow_step_1
        self.persist(annotation)

        assert workflow_step_1.id is not None
        h1 = model.History(name="WorkflowHistory1", user=user)

        invocation_uuid = uuid.uuid1()

        workflow_invocation = model.WorkflowInvocation()
        workflow_invocation.uuid = invocation_uuid
        workflow_invocation.history = h1

        workflow_invocation_step1 = model.WorkflowInvocationStep()
        workflow_invocation_step1.workflow_invocation = workflow_invocation
        workflow_invocation_step1.workflow_step = workflow_step_1

        subworkflow_invocation = model.WorkflowInvocation()
        workflow_invocation.attach_subworkflow_invocation_for_step(workflow_step_2, subworkflow_invocation)

        workflow_invocation_step2 = model.WorkflowInvocationStep()
        workflow_invocation_step2.workflow_invocation = workflow_invocation
        workflow_invocation_step2.workflow_step = workflow_step_2

        workflow_invocation.workflow = workflow

        d1 = self.new_hda(h1, name="1")
        workflow_request_dataset = model.WorkflowRequestToInputDatasetAssociation()
        workflow_request_dataset.workflow_invocation = workflow_invocation
        workflow_request_dataset.workflow_step = workflow_step_1
        workflow_request_dataset.dataset = d1
        self.persist(workflow_invocation)
        assert workflow_request_dataset is not None
        assert workflow_invocation.id is not None

        history_id = h1.id
        self.expunge()

        loaded_invocation = self.query(model.WorkflowInvocation).get(workflow_invocation.id)
        assert loaded_invocation.uuid == invocation_uuid, f"{loaded_invocation.uuid} != {invocation_uuid}"
        assert loaded_invocation
        assert loaded_invocation.history.id == history_id

        step_1, step_2 = loaded_invocation.workflow.steps

        assert not step_1.subworkflow
        assert step_2.subworkflow
        assert len(loaded_invocation.steps) == 2

        subworkflow_invocation_assoc = loaded_invocation.get_subworkflow_invocation_association_for_step(step_2)
        assert subworkflow_invocation_assoc is not None
        assert isinstance(subworkflow_invocation_assoc.subworkflow_invocation, model.WorkflowInvocation)
        assert isinstance(subworkflow_invocation_assoc.parent_workflow_invocation, model.WorkflowInvocation)

        assert subworkflow_invocation_assoc.subworkflow_invocation.history.id == history_id

        loaded_workflow = self.query(model.Workflow).get(workflow_id)
        assert len(loaded_workflow.steps[0].annotations) == 1
        copied_workflow = loaded_workflow.copy(user=user)
        annotations = copied_workflow.steps[0].annotations
        assert len(annotations) == 1

    def test_role_creation(self):
        security_agent = GalaxyRBACAgent(self.model)

        def check_private_role(private_role, email):
            assert private_role.type == self.model.Role.types.PRIVATE
            assert len(private_role.users) == 1
            assert private_role.name == email
            assert private_role.description == "Private Role for " + email

        email = "rule_user_1@example.com"
        u = self.model.User(email=email, password="password")
        self.persist(u)

        role = security_agent.get_private_user_role(u)
        assert role is None
        role = security_agent.create_private_user_role(u)
        assert role is not None
        check_private_role(role, email)

        email = "rule_user_2@example.com"
        u = self.model.User(email=email, password="password")
        self.persist(u)
        role = security_agent.get_private_user_role(u)
        assert role is None
        role = security_agent.get_private_user_role(u, auto_create=True)
        assert role is not None
        check_private_role(role, email)

        # make sure re-running auto_create doesn't break things
        role = security_agent.get_private_user_role(u, auto_create=True)
        assert role is not None
        check_private_role(role, email)

    def test_private_share_role(self):
        security_agent = GalaxyRBACAgent(self.model)

        u_from, u_to, u_other = self._three_users("private_share_role")

        h = self.model.History(name="History for Annotation", user=u_from)
        d1 = self.model.HistoryDatasetAssociation(extension="txt", history=h, create_dataset=True, sa_session=self.model.session)
        self.persist(h, d1)

        security_agent.privately_share_dataset(d1.dataset, [u_to])
        assert security_agent.can_access_dataset(u_to.all_roles(), d1.dataset)
        assert not security_agent.can_access_dataset(u_other.all_roles(), d1.dataset)

    def test_make_dataset_public(self):
        security_agent = GalaxyRBACAgent(self.model)
        u_from, u_to, u_other = self._three_users("make_dataset_public")

        h = self.model.History(name="History for Annotation", user=u_from)
        d1 = self.model.HistoryDatasetAssociation(extension="txt", history=h, create_dataset=True, sa_session=self.model.session)
        self.persist(h, d1)

        security_agent.privately_share_dataset(d1.dataset, [u_to])

        security_agent.make_dataset_public(d1.dataset)
        assert security_agent.can_access_dataset(u_to.all_roles(), d1.dataset)
        assert security_agent.can_access_dataset(u_other.all_roles(), d1.dataset)

    def test_set_all_dataset_permissions(self):
        security_agent = GalaxyRBACAgent(self.model)
        u_from, _, u_other = self._three_users("set_all_perms")

        h = self.model.History(name="History for Annotation", user=u_from)
        d1 = self.model.HistoryDatasetAssociation(extension="txt", history=h, create_dataset=True, sa_session=self.model.session)
        self.persist(h, d1)

        role = security_agent.get_private_user_role(u_from, auto_create=True)
        access_action = security_agent.permitted_actions.DATASET_ACCESS.action
        manage_action = security_agent.permitted_actions.DATASET_MANAGE_PERMISSIONS.action
        permissions = {access_action: [role], manage_action: [role]}
        assert security_agent.can_access_dataset(u_other.all_roles(), d1.dataset)
        security_agent.set_all_dataset_permissions(d1.dataset, permissions)
        assert not security_agent.allow_action(u_other.all_roles(), security_agent.permitted_actions.DATASET_ACCESS, d1.dataset)
        assert not security_agent.can_access_dataset(u_other.all_roles(), d1.dataset)

    def test_can_manage_privately_shared_dataset(self):
        security_agent = GalaxyRBACAgent(self.model)
        u_from, u_to, u_other = self._three_users("can_manage_dataset")

        h = self.model.History(name="History for Prevent Sharing", user=u_from)
        d1 = self.model.HistoryDatasetAssociation(extension="txt", history=h, create_dataset=True, sa_session=self.model.session)
        self.persist(h, d1)

        self._make_owned(security_agent, u_from, d1)
        assert security_agent.can_manage_dataset(u_from.all_roles(), d1.dataset)
        security_agent.privately_share_dataset(d1.dataset, [u_to])
        assert not security_agent.can_manage_dataset(u_to.all_roles(), d1.dataset)

    def test_can_manage_private_dataset(self):
        security_agent = GalaxyRBACAgent(self.model)
        u_from, _, u_other = self._three_users("can_manage_dataset_ps")

        h = self.model.History(name="History for Prevent Sharing", user=u_from)
        d1 = self.model.HistoryDatasetAssociation(extension="txt", history=h, create_dataset=True, sa_session=self.model.session)
        self.persist(h, d1)

        self._make_private(security_agent, u_from, d1)
        assert security_agent.can_manage_dataset(u_from.all_roles(), d1.dataset)
        assert not security_agent.can_manage_dataset(u_other.all_roles(), d1.dataset)

    def _three_users(self, suffix):
        email_from = f"user_{suffix}e1@example.com"
        email_to = f"user_{suffix}e2@example.com"
        email_other = f"user_{suffix}e3@example.com"

        u_from = self.model.User(email=email_from, password="password")
        u_to = self.model.User(email=email_to, password="password")
        u_other = self.model.User(email=email_other, password="password")
        self.persist(u_from, u_to, u_other)
        return u_from, u_to, u_other

    def _make_private(self, security_agent, user, hda):
        role = security_agent.get_private_user_role(user, auto_create=True)
        access_action = security_agent.permitted_actions.DATASET_ACCESS.action
        manage_action = security_agent.permitted_actions.DATASET_MANAGE_PERMISSIONS.action
        permissions = {access_action: [role], manage_action: [role]}
        security_agent.set_all_dataset_permissions(hda.dataset, permissions)

    def _make_owned(self, security_agent, user, hda):
        role = security_agent.get_private_user_role(user, auto_create=True)
        manage_action = security_agent.permitted_actions.DATASET_MANAGE_PERMISSIONS.action
        permissions = {manage_action: [role]}
        security_agent.set_all_dataset_permissions(hda.dataset, permissions)

    def new_hda(self, history, **kwds):
        return history.add_dataset(self.model.HistoryDatasetAssociation(create_dataset=True, sa_session=self.model.session, **kwds))


@skip_if_not_postgres_base
class PostgresMappingTests(MappingTests):

    @classmethod
    def _db_uri(cls):
        base = os.environ.get("GALAXY_TEST_UNIT_MAPPING_URI_POSTGRES_BASE")
        dbname = "gxtest" + str(uuid.uuid4())
        postgres_url = base + dbname
        create_database(postgres_url)
        return postgres_url


class MockObjectStore:

    def __init__(self):
        pass

    def size(self, dataset):
        return 42

    def exists(self, *args, **kwds):
        return True

    def get_filename(self, *args, **kwds):
        return "dataest_14.dat"

    def get_store_by(self, *args, **kwds):
        return 'id'


def get_suite():
    suite = unittest.TestSuite()
    suite.addTest(MappingTests("test_basic"))
    return suite

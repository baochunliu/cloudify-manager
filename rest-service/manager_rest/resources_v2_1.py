#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.
#

import sys
import os
import shutil
import tempfile
from datetime import datetime

from flask import request
from flask.ext.restful_swagger import swagger

from dsl_parser import tasks
from flask_securest.rest_security import SecuredResource
from flask_securest import rest_security

from manager_rest import resources
from manager_rest import resources_v2
from manager_rest import models
from manager_rest import responses_v2_1
from manager_rest import config
from manager_rest import utils
from manager_rest import manager_exceptions
from manager_rest.utils import create_filter_params_list_description
from manager_rest.resources_v2 import create_filters, paginate, sortable
from manager_rest.maintenance import (get_maintenance_file_path,
                                      prepare_maintenance_dict,
                                      get_running_executions)
from manager_rest.manager_exceptions import BadParametersError
from manager_rest.constants import (MAINTENANCE_MODE_ACTIVATED,
                                    MAINTENANCE_MODE_ACTIVATING,
                                    MAINTENANCE_MODE_DEACTIVATED)
from manager_rest.resources import (marshal_with,
                                    exceptions_handled,
                                    verify_json_content_type,
                                    verify_and_convert_bool,
                                    get_blueprints_manager,
                                    CONVENTION_APPLICATION_BLUEPRINT_FILE)
from manager_rest.deployment_update.manager import (
    get_deployment_updates_manager)


def override_marshal_with(f, model):
    @exceptions_handled
    @marshal_with(model)
    def wrapper(*args, **kwargs):
        with resources.skip_nested_marshalling():
            return f(*args, **kwargs)
    return wrapper


class MaintenanceMode(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.MaintenanceMode)
    def get(self, **_):
        maintenance_file_path = get_maintenance_file_path()
        if os.path.isfile(maintenance_file_path):
            state = utils.read_json_file(maintenance_file_path)

            if state['status'] == MAINTENANCE_MODE_ACTIVATED:
                return state
            if state['status'] == MAINTENANCE_MODE_ACTIVATING:
                running_executions = get_running_executions()

                # If there are no running executions,
                # maintenance mode would have been activated at the
                # maintenance handler hook (server.py)
                state['remaining_executions'] = running_executions
                return state
        else:
            return prepare_maintenance_dict(MAINTENANCE_MODE_DEACTIVATED)


class MaintenanceModeAction(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.MaintenanceMode)
    def post(self, maintenance_action, **_):
        maintenance_file_path = get_maintenance_file_path()

        if maintenance_action == 'activate':
            if os.path.isfile(maintenance_file_path):
                state = utils.read_json_file(maintenance_file_path)
                return state, 304

            now = str(datetime.now())

            try:
                user = rest_security.get_username()
            except AttributeError:
                user = ''

            remaining_executions = get_running_executions()
            utils.mkdirs(config.instance().maintenance_folder)
            new_state = prepare_maintenance_dict(
                    status=MAINTENANCE_MODE_ACTIVATING,
                    activation_requested_at=now,
                    remaining_executions=remaining_executions,
                    requested_by=user)
            utils.write_dict_to_json_file(maintenance_file_path, new_state)

            return new_state

        if maintenance_action == 'deactivate':
            if not os.path.isfile(maintenance_file_path):
                return prepare_maintenance_dict(
                        MAINTENANCE_MODE_DEACTIVATED), 304
            os.remove(maintenance_file_path)
            return prepare_maintenance_dict(MAINTENANCE_MODE_DEACTIVATED)

        valid_actions = ['activate', 'deactivate']
        raise BadParametersError(
                'Invalid action: {0}, Valid action '
                'values are: {1}'.format(maintenance_action, valid_actions))


class DeploymentUpdateSteps(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdateStep)
    def post(self, update_id):
        verify_json_content_type()
        request_json = request.json

        manager = get_deployment_updates_manager()
        update_step = \
            manager.create_deployment_update_step(
                    update_id,
                    request_json.get('operation'),
                    request_json.get('entity_type'),
                    request_json.get('entity_id')
            )
        return update_step


class DeploymentUpdates(SecuredResource):
    @swagger.operation(
            responseClass='List[{0}]'.format(
                    responses_v2_1.DeploymentUpdate.__name__),
            nickname="listDeploymentUpdates",
            notes='Returns a list of deployment updates',
            parameters=create_filter_params_list_description(
                    models.DeploymentUpdate.fields,
                    'deployment updates'
            )
    )
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdate)
    @create_filters(models.DeploymentUpdate.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List deployment modification stages
        """
        deployment_updates = \
            get_deployment_updates_manager().deployment_updates_list(
                    include=None, filters=None, pagination=None,
                    sort=None, **kwargs)
        return deployment_updates

    @swagger.operation(
            responseClass=responses_v2_1.DeploymentUpdate,
            nickname="uploadDeploymentUpdate",
            notes="Uploads an archive for staging",
            parameters=[{'name': 'deployment_id',
                         'description': 'The deployment id to update',
                         'required': True,
                         'allowMultiple': False,
                         'dataType': 'string',
                         'paramType': 'query'},
                        {'name': 'application_file_name',
                         'description': 'The name of the app blueprint',
                         'required': False,
                         'allowMultiple': False,
                         'dataType': 'string',
                         'paramType': 'string',
                         'defaultValue': 'blueprint.yaml'},
                        {'name': 'blueprint_archive_url',
                         'description': 'The path of the archive (only if the '
                                        'archive is an online resource',
                         'required': False,
                         'allowMultiple': False,
                         'dataType': 'string',
                         'paramType': 'query'}
                        ]
    )
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdate)
    def post(self, **kwargs):
        """
        Receives an archive to stage. This archive must contain a
        main blueprint file, and specify its name in the application_file_name,
        defaults to 'blueprint.yaml'

        :param kwargs:
        :return: update response
        """
        query_params = request.args
        main_blueprint_key = 'application_file_name'
        blueprint_archive_url_key = 'blueprint_archive_url'
        deployment_id = query_params['deployment_id']

        blueprint_filename = \
            query_params.get(main_blueprint_key,
                             CONVENTION_APPLICATION_BLUEPRINT_FILE)

        temp_dir = tempfile.mkdtemp()
        try:
            archive_destination = \
                os.path.join(temp_dir, "{0}-{1}"
                             .format(deployment_id, blueprint_filename))

            # Saving the archive locally
            utils.save_request_content_to_file(request, archive_destination,
                                               blueprint_archive_url_key,
                                               'blueprint')

            # Unpacking the archive
            relative_app_dir = \
                utils.extract_blueprint_archive_to_mgr(archive_destination,
                                                       temp_dir)

            # retrieving and parsing the blueprint
            temp_app_path = os.path.join(temp_dir, relative_app_dir,
                                         blueprint_filename)

            # TODO: pass resolver and validate_version
            resources_base = '{0}/'.format(
                config.instance().file_server_base_uri)
            blueprint = tasks.parse_dsl(
                'file://{0}'.format(temp_app_path),
                resources_base_url=resources_base)

            # create a staging object
            update = get_deployment_updates_manager(). \
                stage_deployment_update(deployment_id, blueprint)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return update, 201


class DeploymentUpdateCommit(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdate)
    def post(self, update_id):
        manager = get_deployment_updates_manager()
        return manager.commit_deployment_update(update_id)


class DeploymentUpdateFinalizeCommit(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdate)
    def post(self, update_id):
        manager = get_deployment_updates_manager()
        return manager.finalize_commit(update_id)


class Deployments(resources_v2.Deployments):

    get = override_marshal_with(resources_v2.Deployments.get,
                                responses_v2_1.Deployment)


class DeploymentsId(resources.DeploymentsId):

    get = override_marshal_with(resources.DeploymentsId.get,
                                responses_v2_1.Deployment)

    put = override_marshal_with(resources.DeploymentsId.put,
                                responses_v2_1.Deployment)

    delete = override_marshal_with(resources.DeploymentsId.delete,
                                   responses_v2_1.Deployment)


class Nodes(resources_v2.Nodes):

    get = override_marshal_with(resources_v2.Nodes.get,
                                responses_v2_1.Node)


class NodeInstances(resources_v2.NodeInstances):

    get = override_marshal_with(resources_v2.NodeInstances.get,
                                responses_v2_1.NodeInstance)


class NodeInstancesId(resources.NodeInstancesId):

    get = override_marshal_with(resources.NodeInstancesId.get,
                                responses_v2_1.NodeInstance)

    patch = override_marshal_with(resources.NodeInstancesId.patch,
                                  responses_v2_1.NodeInstance)


class PluginsId(resources_v2.PluginsId):

    @swagger.operation(
        responseClass=responses_v2_1.Plugin,
        nickname="deleteById",
        notes="deletes a plugin according to its ID."
    )
    @exceptions_handled
    @marshal_with(responses_v2_1.Plugin)
    def delete(self, plugin_id, **kwargs):
        """
        Delete plugin by ID
        """
        verify_json_content_type()
        request_json = request.json
        force = verify_and_convert_bool('force', request_json.get('force',
                                                                  False))
        try:
            return get_blueprints_manager().remove_plugin(plugin_id=plugin_id,
                                                          force=force)
        except manager_exceptions.ManagerException:
            raise
        except manager_exceptions.ExecutionTimeout:
            tp, ex, tb = sys.exc_info()
            raise manager_exceptions.PluginInstallationTimeout(
                'Timed out during plugin un-installation. ({0}: {1})'
                .format(tp.__name__, ex)), None, tb
        except Exception:
            tp, ex, tb = sys.exc_info()
            raise manager_exceptions.PluginInstallationError(
                'Failed during plugin un-installation. ({0}: {1})'
                .format(tp.__name__, ex)), None, tb

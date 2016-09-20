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

from nose.plugins.attrib import attr

from manager_rest.test.base_test import LATEST_API_VERSION

from .test_base import BaseServerTestCase


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class AuthenticationTests(BaseServerTestCase):

    def test_default_tenant(self):
        self.put_deployment()

        blueprint = self.sm.list_blueprints().items[0]
        self.assertEqual(blueprint.id, 'blueprint')
        self.assertEqual(blueprint.tenant_id, 'default_tenant')

        deployment = self.sm.list_deployments().items[0]
        self.assertEqual(deployment.id, 'deployment')
        self.assertEqual(deployment.tenant_id, 'default_tenant')

        execution = self.sm.list_executions().items[0]
        self.assertEqual(execution.workflow_id,
                         'create_deployment_environment')
        self.assertEqual(execution.tenant_id, 'default_tenant')

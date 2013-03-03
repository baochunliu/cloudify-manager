/*******************************************************************************
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *       http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/
package org.cloudifysource.cosmo.service.state;

import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachine;

import java.net.URI;

/**
 * A touple of instanceId and the agentId that it resides on.
 * @see ServiceDeploymentPlan
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceInstanceDeploymentPlan {

    private URI instanceId;
    private URI agentId;
    private URI serviceId;
    private LifecycleStateMachine stateMachine;

    public URI getInstanceId() {
        return instanceId;
    }

    public void setInstanceId(URI instanceId) {
        this.instanceId = instanceId;
    }

    public URI getAgentId() {
        return agentId;
    }

    public void setAgentId(URI agentId) {
        this.agentId = agentId;
    }

    public LifecycleStateMachine getStateMachine() {
        return stateMachine;
    }

    public void setStateMachine(LifecycleStateMachine stateMachine) {
        this.stateMachine = stateMachine;
    }

    public URI getServiceId() {
        return serviceId;
    }

    public void setServiceId(URI serviceId) {
        this.serviceId = serviceId;
    }
}

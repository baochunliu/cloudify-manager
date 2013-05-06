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
 *******************************************************************************/

package org.cloudifysource.cosmo.orchestrator.integration;

import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.MachineConfiguration;
import org.cloudifysource.cosmo.cloud.driver.MachineDetails;
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.resource.CloudResourceProvisioner;
import org.cloudifysource.cosmo.statecache.RealTimeStateCache;
import org.cloudifysource.cosmo.statecache.RealTimeStateCacheConfiguration;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
import org.mockito.Mockito;
import org.mockito.invocation.InvocationOnMock;
import org.mockito.stubbing.Answer;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.net.URI;
import java.util.Map;
import java.util.concurrent.ExecutionException;

import static org.mockito.Matchers.any;
import static org.mockito.Mockito.when;

/**
 * Tests integration of {@link org.cloudifysource.cosmo.statecache.StateCache} with messaging consumer.
 * @author itaif
 * @since 0.1
 */
public class StateCacheWorkflowMessagingIT {

    // message broker that isolates server
    private MessageBrokerServer broker;
    private URI inputUri;
    private MessageProducer producer;
    private RealTimeStateCache cache;
    private RuoteRuntime runtime;
    private CloudResourceProvisioner provisioner;
    private URI resourceProvisionerTopic;
    private URI stateCacheTopic;
    private CloudDriver cloudDriver;

    @BeforeMethod
    @Parameters({ "port" })
    public void startServer(@Optional("8080") int port) {
        startMessagingBroker(port);
        inputUri = URI.create("http://localhost:" + port + "/input/");
        resourceProvisionerTopic = inputUri.resolve("resource-manager");
        stateCacheTopic = inputUri.resolve("state-cache");
        producer = new MessageProducer();
        startCache();

        Map<String, Object> runtimeProperties = Maps.newHashMap();
        runtimeProperties.put("state_cache", cache);
        runtimeProperties.put("broker_uri", inputUri);
        runtimeProperties.put("message_producer", producer);
        runtime = RuoteRuntime.createRuntime(runtimeProperties);
        startProvisioner();
    }

    @AfterMethod(alwaysRun = true)
    public void stopServer() {
        stopCache();
        stopProvisioner();
        stopMessageBroker();
    }

    private void startCache() {
        RealTimeStateCacheConfiguration config = new RealTimeStateCacheConfiguration();
        config.setMessageTopic(stateCacheTopic);
        cache = new RealTimeStateCache(config);
        cache.start();
    }

    private void startProvisioner() {
        cloudDriver = Mockito.mock(CloudDriver.class);
        provisioner = new CloudResourceProvisioner(cloudDriver, resourceProvisionerTopic);
        provisioner.start();
    }

    private void stopCache() {
        if (cache != null) {
            cache.stop();
        }
    }

    private void stopProvisioner() {
        if (provisioner != null) {
            provisioner.stop();
        }
    }

    private void startMessagingBroker(int port) {
        broker = new MessageBrokerServer();
        broker.start(port);
    }

    private void stopMessageBroker() {
        if (broker != null) {
            broker.stop();
        }
    }

    @Test(timeOut = 10000)
    public void testMessaging() throws ExecutionException, InterruptedException {
        final String resourceId = "node_1";

        // Create radial workflow
        final String flow =
                "define flow\n" +
                "  resource resource_id: \"$resource_id\", action: \"start_machine\"\n" +
                "  state resource_id: \"$resource_id\", reachable: \"true\"\n";
        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(flow, runtime);

        // Configure mock cloud driver
        when(cloudDriver.startMachine(any(MachineConfiguration.class))).thenAnswer(new Answer() {
            @Override
            public Object answer(InvocationOnMock invocation) throws Throwable {
                // Update state cache
                final StateChangedMessage message = newStateChangedMessage(resourceId);
                producer.send(stateCacheTopic, message).get();
                return new MachineDetails(resourceId, "127.0.0.1");
            }
        });

        // Execute workflow
        final Map<String, Object> workitem = Maps.newHashMap();
        workitem.put("resource_id", resourceId);
        final Object workflowId = workflow.asyncExecute(workitem);

        // Wait for workflow to end
        runtime.waitForWorkflow(workflowId);
    }

    private StateChangedMessage newStateChangedMessage(String resourceId) {
        final StateChangedMessage message = new StateChangedMessage();
        message.setResourceId(resourceId);
        message.setState(newState());
        return message;
    }

    private Map<String, Object> newState() {
        Map<String, Object> state = Maps.newLinkedHashMap();
        state.put("reachable", "true");
        return state;
    }


}
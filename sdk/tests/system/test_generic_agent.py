import pytest

from eidos.agent.generic_agent import GenericAgentSpec
from eidos.cpu.conversational_agent_cpu import ConversationalAgentCPUSpec
from eidos.system.resources_base import Resource, Metadata


@pytest.fixture(scope="module")
def generic_agent(caching_llm):
    resource = Resource(apiVersion="eidolon/v1", kind="GenericAgent", metadata=Metadata(name="GenericAgent"),
                        spec=GenericAgentSpec(cpu=dict(spec=ConversationalAgentCPUSpec(llm_unit=caching_llm)),
                                              system_prompt="You are a machine which follows instructions and returns a summary of your actions.",
                                              question_prompt="{{instruction}}",
                                              prompt_properties=dict(instruction=dict(type="string"))))
    return resource


class TestGenericAgent:
    @pytest.fixture(scope="class")
    def client(self, client_builder, generic_agent):
        with client_builder(generic_agent) as client:
            yield client

    def test_can_start(self, client):
        docs = client.get("/docs")
        assert docs.status_code == 200

    def test_llm_calls(self, client):
        post = client.post("/agents/GenericAgent/programs/question", json=dict(instruction="Hi! What would you like to be called?"))
        post.raise_for_status()
        assert post.json()['data']['response'] == "As an AI, I don't have personal preferences, so you can call me "\
                                                  'whatever you feel comfortable with. Most people refer to me as '\
                                                  "'AI' or 'Assistant'."

    def test_continued_conversation(self, client):
        post = client.post("/agents/GenericAgent/programs/question", json=dict(instruction="Hi! my name is Luke"))
        post.raise_for_status()
        process_id = post.json()['process_id']
        follow_up = client.post(f"/agents/GenericAgent/processes/{process_id}/actions/respond", json=dict(statement="Can you sing me Happy Birthday?"))
        follow_up.raise_for_status()
        assert "Luke" in post.json()['data']['response']

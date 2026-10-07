import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from app.services.ai.agent import PetAgentService
from app.services.ai.evidence import evidence


class AgentContextTests(unittest.TestCase):
    def test_actual_agent_payload_contains_selected_pet_and_image_without_invented_sources(self):
        service=PetAgentService.__new__(PetAgentService)
        service.get_messages=lambda *args:[]
        payloads=[]
        async def events(payload,**kwargs):
            payloads.append(payload)
            yield {'event':'on_chat_model_stream','metadata':{'langgraph_node':'model'},'data':{'chunk':SimpleNamespace(content='回答')}}
        service.agent=SimpleNamespace(astream_events=events)
        async def run():
            plain=[event async for event in service.consult('问题','','t','1')]
            selected=[event async for event in service.consult('看图片','https://example.com/cat.png','t','1',{'id':7,'name':'奶糖','bio':'背景'})]
            self.assertIsNone(evidence.get())
            return plain,selected
        plain,selected=asyncio.run(run())
        self.assertEqual(payloads[0]['messages'][-1].content,'问题')
        content=payloads[1]['messages'][-1].content
        self.assertEqual(content[0]['image_url']['url'],'https://example.com/cat.png')
        self.assertIn('奶糖',content[1]['text'])
        self.assertFalse(any(event['event']=='sources' for event in plain+selected))

    def test_manual_rebuild_never_clears_active_collection_first(self):
        service=PetAgentService.__new__(PetAgentService)
        with patch.object(service,'_load_knowledge_base') as load:
            service.rag_clear()
            load.assert_called_once_with(force=True)

    def test_evaluation_does_not_treat_unrecorded_cases_as_passed(self):
        from app.evaluate_ai import evaluate
        cases=[{'id':'cat','question':'猫','expected_sources':['猫.txt'],'review':'核实'},
            {'id':'dog','question':'狗','expected_sources':['狗.txt'],'review':'核实'}]
        empty=evaluate(cases,[])
        self.assertIsNone(empty['source_hit_rate'])
        scored=evaluate(cases,[{'id':'cat','sources':[{'source':'猫.txt'}]}])
        self.assertEqual(scored['rated_cases'],1)
        self.assertFalse(scored['cases'][1]['recorded'])

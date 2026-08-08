
from src.prompt_manager import PromptManager
import logging

def test_prompt_manager_fallback(caplog, capsys):
    with caplog.at_level(logging.WARNING):
        template = "Test {var1} and {missing}"
        result = PromptManager.hydrate_prompt(template, {"var1": "value1"})
        
        assert "value1" in result
        
        # Ensure stdout is empty (no print)
        captured = capsys.readouterr()
        assert captured.out == ""
        
        # Ensure logger caught the warning
        assert "Prompt template variable missing" in caplog.text


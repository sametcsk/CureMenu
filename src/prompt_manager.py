import yaml
import os
from pathlib import Path
from typing import Any, Dict

PROMPTS_DIR = Path(__file__).parent / "prompts"

class PromptManager:
    """
    Tıbbi ajanlar için YAML tabanlı modüler prompt yönetim sistemi.
    TÜBİTAK/Startup standartlarında metadata ve versiyon takibi sağlar.
    """
    
    @classmethod
    def load_prompt(cls, category: str, filename: str) -> Dict[str, Any]:
        """
        Belirtilen kategori (agents, medical, base vb.) altındaki YAML promptunu yükler.
        """
        file_path = PROMPTS_DIR / category / f"{filename}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt dosyası bulunamadı: {file_path}")
            
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data
            
    @classmethod
    def get_agent_prompt(cls, agent_name: str, version: str = "v1") -> str:
        """
        Agent promptunu metadata'dan soyutlayıp sadece content'i döner.
        """
        data = cls.load_prompt("agents", f"{agent_name}_{version}")
        return data.get("content", "")

    @classmethod
    def hydrate_prompt(cls, template: str, kwargs: Dict[str, Any]) -> str:
        """
        Prompt string'i içerisindeki {degisken} kısımlarını doldurur.
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            # Eksik değişkenleri boş string ile değiştir (fail-safe)
            print(f"Uyarı: Prompt içinde beklenen değişken bulunamadı: {e}")
            # Basit bir string formatlaması yapıp eksikleri es geçiyoruz.
            import string
            formatter = string.Formatter()
            return formatter.vformat(template, (), kwargs)

# NimCode Güncelleme ve Test Raporu (v0.8.4 - v0.8.5)

## 1. DeepSeek XML Formatı Entegrasyonu (v0.8.4)
DeepSeek V4 Pro ve Mistral gibi modellerin döndürdüğü `<tool_call name="xyz">` şeklindeki XML attribute formatları için `lenient_parser.py` modülü baştan aşağı güncellendi.
- **Hybrid Parser:** Hem klasik JSON hem de attribute tabanlı XML formatlarını aynı anda destekleyecek bir regex altyapısı kuruldu.
- **Testler:** Tüm eski testler tuple bazlı getiriye göre uyarlandı ve DeepSeek için ekstra test case'ler yazıldı.
- **Sonuç:** Toplamda 224 testin tümü (`pytest tests/`) başarıyla geçti.

## 2. Default Modelin Güncellenmesi (v0.8.5)
Proje genelinde varsayılan model olarak `meta/llama-3.3-70b-instruct` yerine `deepseek-ai/deepseek-v4-pro` atandı.
- `agent.py`, `cli.py`, `config.py`, `nim_client.py` ve `qa_agent.py` içindeki varsayılan parametreler değiştirildi.
- Sürüm numarası `__version__.py` üzerinden `0.8.5`'e çekildi ve README güncellendi.
- Bütün değişiklikler `main` branch'ine pushlanıp `v0.8.5` olarak tag'lendi. 
- Yeni paket lokalde (`pip install .`) kurularak kullanıma hazırlandı.

## 3. Test Projesi ve Planlama Aşaması (`Desktop\test`)
- Nimcode, yeni test projesinde (`Desktop\test`) `git init` komutuyla projeye uygun hale getirildi.
- İlk başta arka planda sessiz çalışırken `prompt_toolkit` nedeniyle kilitlenmelere yol açan stdin hatası (görünmez terminal sorunu) tespit edildi ve çözüldü.
- Nihai olarak kullanıcının ekranında, doğrudan ayrı bir PowerShell penceresinde `/plan` modunda çalışması sağlandı.
- Ajan şu an `LocalPdfToolkitSDD.md` belgesini okuyarak, `.nimcode/plans/active_plan.txt` üzerine kusursuz bir SDD (Software Design Document) mimari şablonu çıkarmak üzere çalışıyor.

*Bu işlemler tamamlandığı için diğer chat'teki (Zenith vb.) görevlerinize güvenle geçiş yapabilirsiniz.*

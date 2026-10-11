"""Estágio 2 (áudio) sem rede e sem GPU: motor falso + ffmpeg real (pulado se ausente)."""
import json
import math
import shutil
import struct
import wave

import pytest

from src.tts import audio, registry, voice_test
from src.tts.audio_io import FORMATO, TAXA, concatenar, duracao_s, para_wav_padrao
from src.tts.base import ErroTTS, config_voz
from src.tts.cache import chave
from src.tts.texto import pedacos

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg ausente")


class FakeEngine:
    nome = "fake"
    clona = False
    exige_ref_text = False
    max_chars = 60
    chamadas: list = []

    def __init__(self, cfg):
        pass

    def versao(self):
        return "fake 1"

    def sintetizar(self, texto, voz, ref_wav, ref_text, saida):
        FakeEngine.chamadas.append((texto, voz, ref_wav))
        n = int(16000 * 0.02 * max(1, len(texto) // 10))  # 16 kHz de propósito: força a conversão
        with wave.open(str(saida), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 8))) for i in range(n)))


class FakeClona(FakeEngine):
    nome = "fakeclone"
    clona = True


class Quebrado(FakeEngine):
    nome = "quebrado"

    def sintetizar(self, *a, **k):
        raise RuntimeError("sem GPU")


registry.registrar("fake", FakeEngine)
registry.registrar("fakeclone", FakeClona, clona=True)
registry.registrar("quebrado", Quebrado)

CONFIG = {"voz": {"engine": "fake", "engines": {"fake": {"professor": "P", "aprendiz": "A"}}}}


@pytest.fixture(autouse=True)
def cache_isolado(tmp_path, monkeypatch):
    """Cada teste com o próprio cache (o padrão fica em ~/.cache, compartilhado)."""
    from src.tts import base
    monkeypatch.setitem(base.DEFAULT_VOZ, "cache_dir", str(tmp_path / "cache_tts"))


def _pasta(tmp_path, lint_ep2="aprovado"):
    pod = tmp_path / "podcast"
    pod.mkdir(parents=True)
    corpo = ("## Abertura\n[Professor]: Em 2024, 95% dos times mediam a latência.\n"
             "[Aprendiz]: Por que tanto?\n## Mecanismo\n[Professor]: Porque o p99 mostra a ponta ruim. "
             "É a parte que a média esconde dos números agregados do painel.\n")
    (pod / "episodio_01_a.md").write_text(f"---\nepisodio: 1\nlint: aprovado\n---\n{corpo}", encoding="utf-8")
    (pod / "episodio_02_b.md").write_text(f"---\nepisodio: 2\nlint: {lint_ep2}\n---\n{corpo}", encoding="utf-8")
    return tmp_path


def test_pedacos_respeita_limite_e_frases():
    texto = "Primeira frase curta. Segunda frase um pouco maior que a primeira! Terceira? " + "palavra " * 30
    ps = pedacos(texto, 60)
    assert all(len(p) <= 60 for p in ps)
    assert ps[0].startswith("Primeira frase curta.")
    assert " ".join(ps).split() == texto.split()          # nada se perde
    assert pedacos("curto", 60) == ["curto"]


def test_conversao_e_concatenacao_com_pausas(tmp_path):
    bruto = tmp_path / "x.raw"
    FakeEngine(None).sintetizar("a" * 50, None, None, None, bruto)
    wav = tmp_path / "x.wav"
    para_wav_padrao(bruto, wav)
    with wave.open(str(wav)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (TAXA, 1, 2)
        d = w.getnframes() / TAXA
    saida = tmp_path / "junto.wav"
    concatenar([wav, 500, wav], saida)
    assert abs(duracao_s(saida) - (2 * d + 0.5)) < 0.02


def test_run_gera_mp3_manifesto_e_usa_cache(tmp_path):
    pasta = _pasta(tmp_path)
    FakeEngine.chamadas.clear()
    r1 = audio.run(CONFIG, str(pasta))
    novas = len(FakeEngine.chamadas)
    assert novas > 0 and [e["episodio"] for e in r1["episodios"]] == [1, 2]
    mp3 = pasta / "podcast/audio/episodio_01_a.mp3"
    man = json.loads((pasta / "podcast/audio/episodio_01_a.json").read_text())
    assert mp3.exists() and man["duracao_s"] > 0
    assert {"engine", "versao_engine", "vozes", "roteiro_sha1", "duracao_s", "data"} <= set(man)   # R34
    assert man["vozes"] == {"professor": "P", "aprendiz": "A"}
    # R19: números normalizados antes da síntese
    falado = " ".join(t for t, _, _ in FakeEngine.chamadas)
    assert "dois mil e vinte e quatro" in falado and "noventa e cinco por cento" in falado and "2024" not in falado
    assert all(len(t) <= FakeEngine.max_chars for t, _, _ in FakeEngine.chamadas)
    # R32: segunda execução, tudo do cache (o ep. 2 tem as mesmas falas do ep. 1 → já veio do cache na 1ª)
    FakeEngine.chamadas.clear()
    r2 = audio.run(CONFIG, str(pasta))
    assert FakeEngine.chamadas == []
    assert all(e["pedacos_sintetizados"] == 0 for e in r2["episodios"])


def test_tmp_interrompido_nao_conta_como_cache(tmp_path):
    pasta = _pasta(tmp_path)
    cache = tmp_path / "cache_tts"
    cache.mkdir(parents=True)
    k = chave("fake", f"fake 1|{FORMATO}", "voz:A", "Por que tanto?")  # fala do Aprendiz
    (cache / f"{k}.wav.tmp").write_bytes(b"parcial")             # R33: sobra de execução interrompida
    FakeEngine.chamadas.clear()
    audio.run(CONFIG, str(pasta), episodios=[1])
    assert any(t == "Por que tanto?" for t, _, _ in FakeEngine.chamadas)
    assert not (cache / f"{k}.wav.tmp").exists() and (cache / f"{k}.wav").exists()


def test_pula_roteiro_reprovado_no_lint(tmp_path):
    r = audio.run(CONFIG, str(_pasta(tmp_path, lint_ep2="reprovado")))   # R28
    assert [e["episodio"] for e in r["episodios"]] == [1]
    assert r["pulados_lint_reprovado"] == [2]
    assert not (tmp_path / "podcast/audio/episodio_02_b.mp3").exists()


def test_episodio_inexistente(tmp_path):
    with pytest.raises(ErroTTS, match="sem roteiro"):
        audio.run(CONFIG, str(_pasta(tmp_path)), episodios=[9])


def test_clone_em_motor_que_nao_clona_para_antes_de_sintetizar(tmp_path):
    ref = tmp_path / "ref.wav"
    FakeEngine(None).sintetizar("x" * 20, None, None, None, ref)
    cfg = {"voz": {**CONFIG["voz"], "clone": {"professor": {"ref_wav": str(ref)}}}}
    FakeEngine.chamadas.clear()
    with pytest.raises(ErroTTS, match="não clona voz") as e:                       # R31
        audio.run(cfg, str(_pasta(tmp_path)))
    assert "xtts" in str(e.value) and FakeEngine.chamadas == []
    with pytest.raises(ErroTTS, match="não encontrado"):
        audio.run({"voz": {"engine": "fakeclone", "clone": {"aprendiz": {"ref_wav": "/nao/existe.wav"}}}},
                  str(_pasta(tmp_path / "b")))
    with pytest.raises(ErroTTS, match="ref_text"):
        audio.validar_clone(registry.get_engine("qwen3", config_voz({})),
                            config_voz({"voz": {"clone": {"professor": {"ref_wav": str(ref)}}}}))


def test_clone_usado_no_motor_que_clona(tmp_path):
    ref = tmp_path / "ref.wav"
    FakeEngine(None).sintetizar("x" * 20, None, None, None, ref)
    cfg = {"voz": {"engine": "fakeclone", "engines": {"fakeclone": {"aprendiz": "A"}},
                   "clone": {"professor": {"ref_wav": str(ref)}}}}
    FakeEngine.chamadas.clear()
    r = audio.run(cfg, str(_pasta(tmp_path)), episodios=[1])
    man = r["episodios"][0]
    assert set(man["clone_sha1"]) == {"professor"} and man["vozes"] == {"aprendiz": "A"}
    assert any(ref_wav == str(ref) for _, _, ref_wav in FakeEngine.chamadas)


def test_voice_test_isola_falhas_e_aplica_clone_so_onde_clona(tmp_path):
    ref = tmp_path / "ref.wav"
    FakeEngine(None).sintetizar("x" * 20, None, None, None, ref)
    cfg = {"voz": {"engines": {"fake": {"professor": "P", "aprendiz": "A"}},
                   "clone": {"professor": {"ref_wav": str(ref)}}}}
    rel = voice_test.run(cfg, saida=str(tmp_path / "tv"), engines=["fake", "quebrado", "naoexiste"])
    ok = {r["engine"]: r["ok"] for r in rel["resultados"]}
    assert ok == {"fake": True, "quebrado": False, "naoexiste": False}          # R37
    assert (tmp_path / "tv/fake.mp3").exists()
    assert json.loads((tmp_path / "tv/relatorio.json").read_text())["resultados"][1]["erro"].startswith("RuntimeError")
    fake = rel["resultados"][0]
    assert fake["vozes"] == {"professor": "P", "aprendiz": "A"} and not fake["clone_sha1"]  # R36


def test_config_voz_mescla_padroes():
    cfg = config_voz({"voz": {"engine": "xtts", "engines": {"xtts": {"professor": "Ana"}}}})
    assert cfg["engine"] == "xtts"
    assert cfg["engines"]["xtts"]["professor"] == "Ana" and cfg["engines"]["xtts"]["max_chars"] == 230
    assert cfg["engines"]["edge"]["aprendiz"] == "pt-BR-FranciscaNeural"
    assert cfg["pausa_ms"]["bloco"] == 700


def test_motores_reais_importam_sem_dependencias_pesadas():
    for nome in ("edge", "xtts", "chatterbox", "qwen3"):
        e = registry.get_engine(nome, config_voz({}))            # import tardio: não carrega torch
        assert e.nome == nome and e.max_chars > 0
    assert registry.engines_que_clonam()[:3] == ["chatterbox", "fakeclone", "qwen3"]

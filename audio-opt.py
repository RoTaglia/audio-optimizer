import os
import subprocess
import numpy as np
import noisereduce as nr
import soundfile as sf
import pyloudnorm as pyln
import matplotlib.pyplot as plt
from tkinter import Tk, filedialog, messagebox, Label, Button, Listbox, Scrollbar, Toplevel, Entry, DoubleVar, Checkbutton, IntVar
from pedalboard import Pedalboard, Compressor, LowShelfFilter, HighShelfFilter, Gain
from pedalboard.io import AudioFile

# CONFIGURAÇÕES PADRÃO
PARAMS = {
    'threshold_db': -16,
    'ratio': 1.8,
    'attack_ms': 10,
    'release_ms': 200,
    'low_gain_db': 3,
    'high_gain_db': 2,
    'gain_db': 1,
    'TARGET_LUFS': -18,
    'MAX_TRUE_PEAK': -1.5,
}

SUPPORTED_EXTENSIONS = ('.mp3', '.wav', '.flac')

# FUNÇÕES PRINCIPAIS

def artistic_mastering(input_path, temp_path, sample_rate=44100):
    with AudioFile(input_path).resampled_to(sample_rate) as f:
        audio = f.read(f.frames)
        sr = f.samplerate

    reduced_noise = nr.reduce_noise(y=audio, sr=sr, stationary=True, prop_decrease=0.6)

    board = Pedalboard([
        Compressor(threshold_db=PARAMS['threshold_db'], ratio=PARAMS['ratio'],
                   attack_ms=PARAMS['attack_ms'], release_ms=PARAMS['release_ms']),
        LowShelfFilter(cutoff_frequency_hz=120, gain_db=PARAMS['low_gain_db'], q=0.7),
        HighShelfFilter(cutoff_frequency_hz=8000, gain_db=PARAMS['high_gain_db'], q=0.7),
        Gain(gain_db=PARAMS['gain_db'])
    ])

    effected = board(reduced_noise, sr)
    peak = np.max(np.abs(effected))
    if peak > 0.99:
        effected *= (0.999 / peak)

    num_channels = effected.shape[0] if effected.ndim > 1 else 1
    with AudioFile(temp_path, 'w', sr, num_channels) as f:
        f.write(effected)

def normalize_lufs_ffmpeg(temp_path, final_path):
    cmd = [
        "ffmpeg", "-y",
        "-i", temp_path,
        "-af", f"loudnorm=I={PARAMS['TARGET_LUFS']}:TP={PARAMS['MAX_TRUE_PEAK']}:LRA=11:print_format=summary",
        "-ar", "44100",
        "-acodec", "pcm_s24le",
        final_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def analyze_loudness(path):
    data, rate = sf.read(path)
    meter = pyln.Meter(rate)
    return meter.integrated_loudness(data)

def generate_report(results, output_dir):
    txt_path = os.path.join(output_dir, "relatorio_masterizacao.txt")
    with open(txt_path, "w", encoding='utf-8') as f:
        f.write("RELATÓRIO DE MASTERIZAÇÃO\n")
        f.write("="*40 + "\n\n")
        for item in results:
            f.write(f"🎵 Track: {item['nome']}\n")
            f.write(f"LUFS final: {item['lufs']:.2f}\n")
            f.write("Etapas aplicadas:\n")
            f.write(" - Redução de ruído\n")
            f.write(" - Equalização com grave/brilho sutis\n")
            f.write(" - Compressão leve\n")
            f.write(f" - Normalização para {PARAMS['TARGET_LUFS']} LUFS\n\n")

    # gráfico
    nomes = [item['nome'] for item in results]
    valores = [item['lufs'] for item in results]
    plt.figure(figsize=(10, 4))
    plt.bar(nomes, valores, color='mediumseagreen')
    plt.axhline(y=PARAMS['TARGET_LUFS'], color='red', linestyle='--', label=f"Target: {PARAMS['TARGET_LUFS']} LUFS")
    plt.xticks(rotation=45, ha='right')
    plt.ylabel("LUFS")
    plt.title("Loudness Final por Track")
    plt.tight_layout()
    plt.legend()
    plot_path = os.path.join(output_dir, "grafico_lufs.png")
    plt.savefig(plot_path)
    plt.close()

    return txt_path, plot_path

def mostrar_resultado(txt_path, plot_path):
    with open(txt_path, encoding='utf-8') as f:
        conteudo = f.read()

    janela = Toplevel()
    janela.title("Relatório de Masterização")
    Label(janela, text="Relatório:", font=('Arial', 14, 'bold')).pack(pady=5)
    from tkinter.scrolledtext import ScrolledText
    txt = ScrolledText(janela, width=80, height=20)
    txt.insert('1.0', conteudo)
    txt.config(state='disabled')
    txt.pack(padx=10, pady=5)

def abrir_configuracoes():
    janela = Toplevel()
    janela.title("Configurações de Masterização")
    entradas = {}

    def resetar():
        for key, var in entradas.items():
            var.set(PARAMS_DEFAULT[key])

    PARAMS_DEFAULT = {
        'threshold_db': -16,
        'ratio': 1.8,
        'attack_ms': 10,
        'release_ms': 200,
        'low_gain_db': 3,
        'high_gain_db': 2,
        'gain_db': 1,
        'TARGET_LUFS': -18,
        'MAX_TRUE_PEAK': -1.5,
    }

    for i, (param, default) in enumerate(PARAMS.items()):
        Label(janela, text=param).grid(row=i, column=0, sticky='e')
        var = DoubleVar(value=default)
        Entry(janela, textvariable=var, width=10).grid(row=i, column=1)
        entradas[param] = var

    def salvar_config():
        for chave, var in entradas.items():
            try:
                valor = float(var.get())
                PARAMS[chave] = valor
            except ValueError:
                messagebox.showerror("Erro", f"Valor inválido para {chave}. Use números.")
                return
        messagebox.showinfo("Salvo", "Parâmetros atualizados com sucesso.")
        janela.destroy()

    Button(janela, text="Salvar", command=salvar_config).grid(row=len(PARAMS), column=0, pady=10)
    Button(janela, text="Resetar", command=resetar).grid(row=len(PARAMS), column=1)

# VARIÁVEIS DE ESTADO
checkboxes = []
arquivos = []
pasta_selecionada = ""

def selecionar_pasta():
    global pasta_selecionada, checkboxes, arquivos
    pasta_selecionada = filedialog.askdirectory()
    if not pasta_selecionada:
        return

    arquivos = [f for f in os.listdir(pasta_selecionada)
                if f.lower().endswith(SUPPORTED_EXTENSIONS)]

    if not arquivos:
        messagebox.showinfo("Nada encontrado", "Não foram encontrados arquivos suportados.")
        return

    lista_window = Toplevel()
    lista_window.title("Selecionar Arquivos")
    Label(lista_window, text="Marque os arquivos que deseja processar:").pack(pady=5)

    frame = lista_window
    checkboxes.clear()
    for f in arquivos:
        var = IntVar(value=1)
        chk = Checkbutton(frame, text=f, variable=var)
        chk.pack(anchor='w')
        checkboxes.append((f, var))

    Button(lista_window, text="Começar Masterização", command=processar_selecionados).pack(pady=10)

def processar_selecionados():
    selecionados = [f for f, v in checkboxes if v.get() == 1]
    if not selecionados:
        messagebox.showwarning("Nenhum selecionado", "Selecione ao menos um arquivo para processar.")
        return

    output_dir = os.path.join(pasta_selecionada, "masterizados")
    os.makedirs(output_dir, exist_ok=True)
    resultados = []

    for file in selecionados:
        full_path = os.path.join(pasta_selecionada, file)
        base_name = os.path.splitext(file)[0]
        temp_path = os.path.join(output_dir, f"{base_name}_temp.wav")
        final_path = os.path.join(output_dir, f"{base_name}_master.wav")

        print(f"🎧 Processando: {file}")
        artistic_mastering(full_path, temp_path)
        normalize_lufs_ffmpeg(temp_path, final_path)
        os.remove(temp_path)

        lufs = analyze_loudness(final_path)
        resultados.append({'nome': base_name, 'lufs': lufs})

    txt_path, plot_path = generate_report(resultados, output_dir)
    mostrar_resultado(txt_path, plot_path)
    messagebox.showinfo("Finalizado", f"Arquivos processados e relatório salvo em:\n{output_dir}")

# INTERFACE PRINCIPAL
root = Tk()
root.title("Masterizador Automático de Áudio")
root.geometry("400x180")
root.resizable(False, False)

Label(root, text="Escolha uma pasta com arquivos de áudio para masterizar", wraplength=380).pack(pady=10)
Button(root, text="Selecionar Pasta", command=selecionar_pasta, bg="#4CAF50", fg="white", font=("Arial", 12)).pack(pady=5)
Button(root, text="Configurações", command=abrir_configuracoes, font=("Arial", 12)).pack(pady=5)

root.mainloop()

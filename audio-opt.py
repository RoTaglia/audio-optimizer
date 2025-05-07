import os
import subprocess
import numpy as np
import noisereduce as nr
import soundfile as sf
import pyloudnorm as pyln
import matplotlib.pyplot as plt
from tkinter import Tk, filedialog, messagebox, Label, Button, Listbox, Scrollbar, Toplevel, Entry, DoubleVar, Checkbutton, IntVar, LabelFrame, Frame, Canvas
from pedalboard import Pedalboard, Compressor, LowShelfFilter, HighShelfFilter, Gain, Chorus, Reverb
from pedalboard.io import AudioFile

# CONFIGURAÇÕES PADRÃO
PARAMS = {
    # Parâmetros de compressão
    'threshold_db': -14,
    'ratio': 2.5,
    'attack_ms': 20,
    'release_ms': 250,
    
    # Parâmetros de equalização
    'low_gain_db': 4,
    'low_cutoff_hz': 120,
    'high_gain_db': 3,
    'high_cutoff_hz': 8000,
    
    # Parâmetros de efeitos
    'reverb_amount': 0.15,
    'reverb_room_size': 0.5,
    'chorus_amount': 0.1,
    'chorus_rate_hz': 0.8,
    'tape_saturation': 0.08,
    
    # Parâmetros de masterização
    'gain_db': 1,
    'TARGET_LUFS': -16,
    'MAX_TRUE_PEAK': -1.0,
    'SAMPLE_RATE': 48000
}

SUPPORTED_EXTENSIONS = ('.mp3', '.wav', '.flac')

# FUNÇÕES PRINCIPAIS

def artistic_mastering(input_path, temp_path):
    with AudioFile(input_path).resampled_to(PARAMS['SAMPLE_RATE']) as f:
        audio = f.read(f.frames)
        sr = f.samplerate

    board = Pedalboard([
        Compressor(
            threshold_db=PARAMS['threshold_db'],
            ratio=PARAMS['ratio'],
            attack_ms=PARAMS['attack_ms'],
            release_ms=PARAMS['release_ms']
        ),
        LowShelfFilter(
            cutoff_frequency_hz=PARAMS['low_cutoff_hz'],
            gain_db=PARAMS['low_gain_db'],
            q=0.7
        ),
        HighShelfFilter(
            cutoff_frequency_hz=PARAMS['high_cutoff_hz'],
            gain_db=PARAMS['high_gain_db'],
            q=0.7
        ),
        Chorus(
            rate_hz=PARAMS['chorus_rate_hz'],
            depth=0.25,
            mix=PARAMS['chorus_amount']
        ),
        Reverb(
            room_size=PARAMS['reverb_room_size'],
            damping=0.7,
            wet_level=PARAMS['reverb_amount']
        ),
        Gain(gain_db=PARAMS['gain_db'])
    ])

    effected = board(audio, sr)
    peak = np.max(np.abs(effected))
    if peak > (10 ** (PARAMS['MAX_TRUE_PEAK'] / 20)):
        effected *= (10 ** (PARAMS['MAX_TRUE_PEAK'] / 20)) / peak

    with AudioFile(temp_path, 'w', sr, effected.shape[0]) as f:
        f.write(effected)

def normalize_lufs_ffmpeg(temp_path, final_path):
    cmd = [
        "ffmpeg", "-y",
        "-i", temp_path,
        "-af", f"loudnorm=I={PARAMS['TARGET_LUFS']}:TP={PARAMS['MAX_TRUE_PEAK']}:LRA=11:print_format=summary",
        "-ar", str(PARAMS['SAMPLE_RATE']),  # Use o valor configurado
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
    janela.geometry("220x650")
    
    # Criando um canvas e scrollbar para permitir rolagem
    canvas = Canvas(janela)
    scrollbar = Scrollbar(janela, orient="vertical", command=canvas.yview)
    scrollable_frame = Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        )
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    entradas = {}
    row = 0

    # Função para criar linhas de parâmetros
    def criar_parametro(parent, param, value, r):
        Label(parent, text=param.replace('_', ' ').title() + ":").grid(row=r, column=0, sticky='e', padx=5, pady=2)
        if param == 'SAMPLE_RATE':
            var = IntVar(value=value)
        else:
            var = DoubleVar(value=value)
        Entry(parent, textvariable=var, width=10).grid(row=r, column=1, sticky='w', padx=5, pady=2)
        entradas[param] = var
        return r + 1

    # Adicionando seções de parâmetros
    sections = [
        ("Compressão", ['threshold_db', 'ratio', 'attack_ms', 'release_ms']),
        ("Equalização", ['low_gain_db', 'low_cutoff_hz', 'high_gain_db', 'high_cutoff_hz']),
        ("Efeitos", ['reverb_amount', 'reverb_room_size', 'chorus_amount', 'chorus_rate_hz', 'tape_saturation']),
        ("Masterização", ['gain_db', 'TARGET_LUFS', 'MAX_TRUE_PEAK', 'SAMPLE_RATE'])
    ]

    for section, params in sections:
        frame = LabelFrame(scrollable_frame, text=section, padx=5, pady=5)
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        row += 1
        
        inner_row = 0
        for param in params:
            inner_row = criar_parametro(frame, param, PARAMS[param], inner_row)
        row += inner_row

    # Funções de controle
    def resetar():
        defaults = {
            'threshold_db': -14,
            'ratio': 2.5,
            'attack_ms': 20,
            'release_ms': 250,
            'low_gain_db': 4,
            'low_cutoff_hz': 120,
            'high_gain_db': 3,
            'high_cutoff_hz': 8000,
            'reverb_amount': 0.15,
            'reverb_room_size': 0.5,
            'chorus_amount': 0.1,
            'chorus_rate_hz': 0.8,
            'tape_saturation': 0.08,
            'gain_db': 1,
            'TARGET_LUFS': -16,
            'MAX_TRUE_PEAK': -1.0,
            'SAMPLE_RATE': 48000
        }
        for key, var in entradas.items():
            var.set(defaults[key])

    def salvar_config():
        for chave, var in entradas.items():
            try:
                if chave == 'SAMPLE_RATE':
                    PARAMS[chave] = int(var.get())
                else:
                    PARAMS[chave] = float(var.get())
            except ValueError:
                messagebox.showerror("Erro", f"Valor inválido para {chave}. Use números.")
                return
        messagebox.showinfo("Salvo", "Parâmetros atualizados com sucesso!")
        janela.destroy()

    # Frame para botões
    btn_frame = Frame(scrollable_frame)
    btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
    
    Button(btn_frame, text="Salvar", command=salvar_config).grid(row=0, column=0, padx=5)
    Button(btn_frame, text="Resetar", command=resetar).grid(row=0, column=1, padx=5)
    Button(btn_frame, text="Cancelar", command=janela.destroy).grid(row=0, column=2, padx=5)
    
# VARIÁVEIS DE ESTADO
checkboxes = []
arquivos = []
pasta_selecionada = ""

def selecionar_pasta():
    global pasta_selecionada, checkboxes, arquivos

    pasta_selecionada = filedialog.askdirectory()
    if not pasta_selecionada:
        return

    arquivos = obter_arquivos_suportados(pasta_selecionada)
    if not arquivos:
        messagebox.showinfo("Nada encontrado", "Não foram encontrados arquivos suportados.")
        return

    exibir_selecao_arquivos(arquivos)

def obter_arquivos_suportados(pasta):
    return [f for f in os.listdir(pasta) if f.lower().endswith(SUPPORTED_EXTENSIONS)]

def exibir_selecao_arquivos(arquivos):
    global checkboxes
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

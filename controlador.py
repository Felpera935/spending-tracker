import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import math
from datetime import datetime

CATEGORIAS = [
    "20% guardar", "Condominio", "Aluguel", "Terapia",
    "Agua e luz e Gás", "Internet", "Cursos Medicina",
    "Restaurante/padaria", "IFOOD", "Mercado", "Uber",
    "Combustível", "Farmácia/saúde", "Academia",
    "Desejos e Mimos", "Lazer", "Descontos salário",
    "Presentes/Inscrições", "Outros"
]

# Cores do gráfico de pizza (paleta que continua distinguível para daltônicos).
# As 7 maiores categorias do mês ganham cor própria; o resto vira uma fatia cinza.
CORES_PIZZA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
COR_DEMAIS = "#a8a69f"
COR_FUNDO_GRAFICO = "#ffffff"
COR_TEXTO = "#0b0b0b"
COR_TEXTO_SUAVE = "#52514e"
CORES_COM_TEXTO_ESCURO = {"#eda100", "#e87ba4", COR_DEMAIS}  # fatias claras pedem texto escuro


def normalizar_mes(texto):
    """Aceita '1/2026', '01/2026', '1/26' ou '01-2026' e devolve sempre 'MM/AAAA'.

    Sem isso, '1/2026' e '01/2026' virariam meses diferentes e os totais se dividiriam.
    """
    partes = texto.strip().replace("-", "/").split("/")
    if len(partes) != 2 or not all(p.strip().isdigit() for p in partes):
        raise ValueError(f"Mês/Ano inválido: {texto!r}")
    mes, ano_txt = int(partes[0]), partes[1].strip()
    ano = int(ano_txt) + 2000 if len(ano_txt) == 2 else int(ano_txt)
    if not 1 <= mes <= 12 or not 1900 <= ano <= 2999:
        raise ValueError(f"Mês/Ano inválido: {texto!r}")
    return f"{mes:02d}/{ano}"


def montar_fatias(totais, max_cores=len(CORES_PIZZA)):
    """Recebe [(categoria, total)] e devolve (fatias, legenda).

    legenda: todas as categorias com gasto, da maior para a menor, cada uma com sua cor.
    fatias:  as `max_cores` maiores + uma fatia cinza somando as demais (se houver).
    """
    itens = sorted(((c, v) for c, v in totais if v > 0), key=lambda item: item[1], reverse=True)
    legenda = [(c, v, CORES_PIZZA[i] if i < max_cores else COR_DEMAIS) for i, (c, v) in enumerate(itens)]
    fatias = legenda[:max_cores]
    resto = legenda[max_cores:]
    if len(resto) == 1:
        fatias.append(resto[0])
    elif resto:
        fatias.append((f"Demais ({len(resto)})", sum(v for _, v, _ in resto), COR_DEMAIS))
    return fatias, legenda

class AppControleGastos:
    def __init__(self, root):
        self.root = root
        self.root.title("Controle Financeiro")
        self.root.geometry("620x660")

        self.id_gasto_editando = None # Controle para saber se está editando
        self.avisos_agendados = {}    # Timers dos avisos que somem sozinhos

        self.conectar_db()
        self.normalizar_meses_existentes()
        self.criar_interface()
        self.atualizar_lista_gastos()
        self.atualizar_acumulado()
        self.atualizar_resumo()

    def conectar_db(self):
        self.conn = sqlite3.connect("dados_financeiros.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS gastos 
                            (id INTEGER PRIMARY KEY, mes_ano TEXT, categoria TEXT, valor REAL)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS renda 
                            (mes_ano TEXT PRIMARY KEY, valor REAL)''')
        self.conn.commit()

    def criar_interface(self):
        abas = ttk.Notebook(self.root)
        abas.pack(expand=1, fill="both", padx=10, pady=10)

        # ================= ABA 1: Lançar e Editar Gastos =================
        aba_gastos = ttk.Frame(abas)
        abas.add(aba_gastos, text="Lançar/Editar Gasto")

        ttk.Label(aba_gastos, text="Mês/Ano (ex: 10/2026):").pack(pady=(10, 0))
        self.mes_gasto = ttk.Entry(aba_gastos)
        self.mes_gasto.insert(0, datetime.now().strftime("%m/%Y"))
        self.mes_gasto.pack()
        self.mes_gasto.bind('<KeyRelease>', lambda e: self.atualizar_acumulado())

        ttk.Label(aba_gastos, text="Categoria:").pack(pady=(5, 0))
        self.combo_categoria = ttk.Combobox(aba_gastos, values=CATEGORIAS, state="readonly")
        self.combo_categoria.pack()
        self.combo_categoria.bind('<<ComboboxSelected>>', lambda e: self.atualizar_acumulado())

        # Quanto já foi gasto na categoria escolhida (ou no mês todo) até agora
        self.label_acumulado = ttk.Label(aba_gastos, text="", font=("", 10, "bold"))
        self.label_acumulado.pack(pady=(4, 0))

        ttk.Label(aba_gastos, text="Valor (R$):").pack(pady=(5, 0))
        self.valor_gasto = ttk.Entry(aba_gastos)
        self.valor_gasto.pack()

        # Botões de ação do Gasto
        btn_frame = ttk.Frame(aba_gastos)
        btn_frame.pack(pady=10)
        
        self.btn_salvar = ttk.Button(btn_frame, text="Registrar Novo", command=self.salvar_gasto)
        self.btn_salvar.pack(side=tk.LEFT, padx=5)
        
        self.btn_cancelar_edicao = ttk.Button(btn_frame, text="Cancelar Edição", command=self.limpar_campos_gasto, state=tk.DISABLED)
        self.btn_cancelar_edicao.pack(side=tk.LEFT, padx=5)

        self.btn_excluir = ttk.Button(btn_frame, text="Excluir Gasto", command=self.excluir_gasto, state=tk.DISABLED)
        self.btn_excluir.pack(side=tk.LEFT, padx=5)

        # Aviso sutil (sem pop-up)
        self.status_gasto = ttk.Label(aba_gastos, text="", foreground="green")
        self.status_gasto.pack()

        # Tabela (Histórico visual de gastos)
        ttk.Label(aba_gastos, text="Histórico de Gastos Cadastrados (Clique para editar):", font=("", 9, "italic")).pack(pady=(10,0))
        self.tree = ttk.Treeview(aba_gastos, columns=('id', 'mes', 'categoria', 'valor'), show='headings', height=8)
        self.tree.column('id', width=0, stretch=tk.NO) # Esconde o ID
        self.tree.heading('mes', text='Mês')
        self.tree.column('mes', width=80, anchor=tk.CENTER)
        self.tree.heading('categoria', text='Categoria')
        self.tree.column('categoria', width=180)
        self.tree.heading('valor', text='Valor (R$)')
        self.tree.column('valor', width=100, anchor=tk.E)
        self.tree.pack(pady=5, fill=tk.X, padx=10)
        self.tree.bind('<ButtonRelease-1>', self.preencher_edicao)

        # ================= ABA 2: Resumo do Mês (gráfico de pizza) =================
        aba_resumo = ttk.Frame(abas)
        abas.add(aba_resumo, text="Resumo do Mês")

        linha_mes = ttk.Frame(aba_resumo)
        linha_mes.pack(pady=(10, 0))
        ttk.Label(linha_mes, text="Mês/Ano:").pack(side=tk.LEFT, padx=(0, 5))
        self.mes_resumo = ttk.Entry(linha_mes, width=10)
        self.mes_resumo.insert(0, datetime.now().strftime("%m/%Y"))
        self.mes_resumo.pack(side=tk.LEFT)
        self.mes_resumo.bind('<Return>', lambda e: self.atualizar_resumo())
        ttk.Button(linha_mes, text="Atualizar", command=self.atualizar_resumo).pack(side=tk.LEFT, padx=5)

        self.label_total_resumo = ttk.Label(aba_resumo, text="", font=("", 12, "bold"))
        self.label_total_resumo.pack(pady=(10, 0))
        self.label_renda_resumo = ttk.Label(aba_resumo, text="", foreground=COR_TEXTO_SUAVE)
        self.label_renda_resumo.pack()

        self.canvas_pizza = tk.Canvas(aba_resumo, width=580, height=440, bg=COR_FUNDO_GRAFICO,
                                      highlightthickness=0)
        self.canvas_pizza.pack(pady=10)

        # O resumo também se atualiza sempre que a aba é aberta
        abas.bind('<<NotebookTabChanged>>', lambda e: self.atualizar_resumo())

        # ================= ABA 3: Renda Mensal =================
        aba_renda = ttk.Frame(abas)
        abas.add(aba_renda, text="Renda do Mês")

        ttk.Label(aba_renda, text="Mês/Ano (ex: 10/2026):").pack(pady=5)
        self.mes_renda = ttk.Entry(aba_renda)
        self.mes_renda.insert(0, datetime.now().strftime("%m/%Y"))
        self.mes_renda.pack()

        ttk.Label(aba_renda, text="Renda Total (R$):").pack(pady=5)
        self.valor_renda = ttk.Entry(aba_renda)
        self.valor_renda.pack()

        ttk.Button(aba_renda, text="Salvar Renda", command=self.salvar_renda).pack(pady=15)
        self.status_renda = ttk.Label(aba_renda, text="", foreground="green")
        self.status_renda.pack()

        # ================= ABA 4: Relatório =================
        aba_relatorio = ttk.Frame(abas)
        abas.add(aba_relatorio, text="Relatório Mensal")

        ttk.Label(aba_relatorio, text="Mês/Ano para consulta:").pack(pady=5)
        self.mes_relatorio = ttk.Entry(aba_relatorio)
        self.mes_relatorio.insert(0, datetime.now().strftime("%m/%Y"))
        self.mes_relatorio.pack()

        ttk.Button(aba_relatorio, text="Gerar Relatório", command=self.gerar_relatorio).pack(pady=10)

        self.texto_relatorio = tk.Text(aba_relatorio, height=15, width=55, state="disabled")
        self.texto_relatorio.pack(pady=5)

        # ================= ABA 5: Configurações =================
        aba_config = ttk.Frame(abas)
        abas.add(aba_config, text="Configurações")
        
        ttk.Label(aba_config, text="Área de Risco", font=("", 12, "bold")).pack(pady=(30, 10))
        ttk.Label(aba_config, text="Essa opção apagará o banco de dados inteiro.\nUse apenas se quiser começar tudo do zero.").pack(pady=5)
        
        btn_apagar = tk.Button(aba_config, text="LIMPAR TODOS OS DADOS", bg="red", fg="white", command=self.limpar_dados)
        btn_apagar.pack(pady=20)

    # =============== FUNÇÕES ===============
    
    def salvar_gasto(self):
        mes = self.ler_mes(self.mes_gasto)
        if mes is None:
            return
        categoria = self.combo_categoria.get()
        try:
            valor = float(self.valor_gasto.get().replace(',', '.'))
            if not categoria:
                raise ValueError("vazio")

            if self.id_gasto_editando:
                # Atualiza gasto existente
                self.cursor.execute("UPDATE gastos SET mes_ano=?, categoria=?, valor=? WHERE id=?",
                                    (mes, categoria, valor, self.id_gasto_editando))
                acao = "Gasto atualizado!"
            else:
                # Cria um novo gasto
                self.cursor.execute("INSERT INTO gastos (mes_ano, categoria, valor) VALUES (?, ?, ?)",
                                    (mes, categoria, valor))
                acao = "Gasto salvo!"

            self.conn.commit()

            # Mostra na hora quanto essa categoria já soma no mês (ex.: combustível)
            total, qtd = self.total_gastos(mes, categoria)
            plural = "s" if qtd != 1 else ""
            self.mostrar_aviso(self.status_gasto,
                               f"{acao} {categoria} em {mes} já soma R$ {total:.2f} ({qtd} lançamento{plural})",
                               duracao=6000)

            self.limpar_campos_gasto()
            self.atualizar_lista_gastos()

            # O gráfico passa a mostrar o mês do gasto que acabou de ser salvo
            self.mes_resumo.delete(0, tk.END)
            self.mes_resumo.insert(0, mes)
            self.atualizar_resumo()

        except ValueError:
            messagebox.showerror("Erro", "Insira um valor numérico válido e selecione uma categoria.")

    def preencher_edicao(self, event):
        item = self.tree.focus()
        if not item: return
        valores = self.tree.item(item, 'values')
        if valores:
            self.id_gasto_editando = valores[0]
            
            self.mes_gasto.delete(0, tk.END)
            self.mes_gasto.insert(0, valores[1])
            
            self.combo_categoria.set(valores[2])
            
            self.valor_gasto.delete(0, tk.END)
            self.valor_gasto.insert(0, valores[3])
            
            # Muda os botões para modo de edição
            self.btn_salvar.config(text="Atualizar Gasto")
            self.btn_cancelar_edicao.config(state=tk.NORMAL)
            self.btn_excluir.config(state=tk.NORMAL)
            self.atualizar_acumulado()

    def excluir_gasto(self):
        if self.id_gasto_editando:
            self.cursor.execute("DELETE FROM gastos WHERE id=?", (self.id_gasto_editando,))
            self.conn.commit()
            self.limpar_campos_gasto()
            self.atualizar_lista_gastos()
            self.atualizar_resumo()
            self.mostrar_aviso(self.status_gasto, "Gasto excluído!")

    def limpar_campos_gasto(self):
        self.id_gasto_editando = None
        self.valor_gasto.delete(0, tk.END)
        self.combo_categoria.set('')
        
        # Volta os botões pro modo normal
        self.btn_salvar.config(text="Registrar Novo")
        self.btn_cancelar_edicao.config(state=tk.DISABLED)
        self.btn_excluir.config(state=tk.DISABLED)
        self.atualizar_acumulado()

    def atualizar_lista_gastos(self):
        # Limpa a tabela
        for row in self.tree.get_children():
            self.tree.delete(row)
        # Busca os últimos cadastros
        self.cursor.execute("SELECT id, mes_ano, categoria, valor FROM gastos ORDER BY id DESC")
        for linha in self.cursor.fetchall():
            self.tree.insert('', tk.END, values=(linha[0], linha[1], linha[2], f"{linha[3]:.2f}"))

    def salvar_renda(self):
        mes = self.ler_mes(self.mes_renda)
        if mes is None:
            return
        try:
            valor = float(self.valor_renda.get().replace(',', '.'))
            self.cursor.execute("REPLACE INTO renda (mes_ano, valor) VALUES (?, ?)", (mes, valor))
            self.conn.commit()
            self.mostrar_aviso(self.status_renda, "Renda salva com sucesso!")
            self.atualizar_resumo()
        except ValueError:
            messagebox.showerror("Erro", "Insira um valor numérico válido.")

    def mostrar_aviso(self, label, texto, duracao=2500):
        # Cancela o timer do aviso anterior, senão ele apagaria este antes da hora
        anterior = self.avisos_agendados.get(str(label))
        if anterior:
            self.root.after_cancel(anterior)
        label.config(text=texto)
        # Apaga o texto depois de `duracao` milissegundos
        self.avisos_agendados[str(label)] = self.root.after(duracao, lambda: label.config(text=""))

    def gerar_relatorio(self):
        mes = self.ler_mes(self.mes_relatorio)
        if mes is None:
            return

        self.cursor.execute("SELECT valor FROM renda WHERE mes_ano = ?", (mes,))
        renda_resultado = self.cursor.fetchone()
        renda = renda_resultado[0] if renda_resultado else 0.0

        self.cursor.execute("SELECT categoria, SUM(valor) FROM gastos WHERE mes_ano = ? GROUP BY categoria", (mes,))
        gastos_por_categoria = self.cursor.fetchall()
        
        gasto_total = sum(valor for _, valor in gastos_por_categoria)

        texto = f"--- RELATÓRIO DE {mes} ---\n"
        texto += f"Renda do Mês: R$ {renda:.2f}\n"
        texto += f"Gasto Total: R$ {gasto_total:.2f}\n"
        texto += f"Saldo Restante: R$ {renda - gasto_total:.2f}\n\n"
        texto += "--- DETALHAMENTO POR SEGMENTO ---\n"

        if gastos_por_categoria:
            for cat, valor in gastos_por_categoria:
                pct_gasto = (valor / gasto_total) * 100 if gasto_total > 0 else 0
                pct_salario = (valor / renda) * 100 if renda > 0 else 0
                
                texto += f"• {cat}: R$ {valor:.2f}\n"
                texto += f"  (Representa {pct_gasto:.1f}% dos gastos e {pct_salario:.1f}% da renda)\n"
        else:
            texto += "Nenhum gasto registrado neste mês."

        self.texto_relatorio.config(state="normal")
        self.texto_relatorio.delete("1.0", tk.END)
        self.texto_relatorio.insert(tk.END, texto)
        self.texto_relatorio.config(state="disabled")

    def limpar_dados(self):
        resposta = messagebox.askyesno("Apagar Tudo", "Tem certeza que deseja APAGAR TODOS OS DADOS do aplicativo? Isso não pode ser desfeito.")
        if resposta:
            self.cursor.execute("DELETE FROM gastos")
            self.cursor.execute("DELETE FROM renda")
            self.conn.commit()
            self.atualizar_lista_gastos()
            self.atualizar_acumulado()
            self.atualizar_resumo()
            self.texto_relatorio.config(state="normal")
            self.texto_relatorio.delete("1.0", tk.END)
            self.texto_relatorio.config(state="disabled")
            messagebox.showinfo("Sucesso", "Todos os dados foram apagados permanentemente.")

    # =============== TOTAIS ACUMULADOS E GRÁFICO ===============

    def ler_mes(self, campo):
        """Lê e padroniza o Mês/Ano de um campo. Mostra erro e devolve None se for inválido."""
        try:
            mes = normalizar_mes(campo.get())
        except ValueError:
            messagebox.showerror("Erro", "Mês/Ano inválido. Use o formato MM/AAAA, por exemplo 10/2026.")
            return None
        campo.delete(0, tk.END)
        campo.insert(0, mes)
        return mes

    def normalizar_meses_existentes(self):
        """Padroniza meses já salvos (ex.: '1/2026' -> '01/2026') para os totais baterem."""
        self.cursor.execute("SELECT DISTINCT mes_ano FROM gastos")
        for (mes,) in self.cursor.fetchall():
            try:
                novo = normalizar_mes(mes)
            except ValueError:
                continue
            if novo != mes:
                self.cursor.execute("UPDATE gastos SET mes_ano=? WHERE mes_ano=?", (novo, mes))
        # Na renda o mês é a chave: só renomeia se ainda não existir o mês padronizado
        self.cursor.execute("SELECT mes_ano FROM renda")
        for (mes,) in self.cursor.fetchall():
            try:
                novo = normalizar_mes(mes)
            except ValueError:
                continue
            if novo != mes and not self.cursor.execute(
                    "SELECT 1 FROM renda WHERE mes_ano=?", (novo,)).fetchone():
                self.cursor.execute("UPDATE renda SET mes_ano=? WHERE mes_ano=?", (novo, mes))
        self.conn.commit()

    def total_gastos(self, mes, categoria=None):
        """Soma e quantidade de gastos do mês (de uma categoria, ou de todas)."""
        if categoria:
            self.cursor.execute("SELECT COALESCE(SUM(valor), 0), COUNT(*) FROM gastos "
                                "WHERE mes_ano = ? AND categoria = ?", (mes, categoria))
        else:
            self.cursor.execute("SELECT COALESCE(SUM(valor), 0), COUNT(*) FROM gastos "
                                "WHERE mes_ano = ?", (mes,))
        total, qtd = self.cursor.fetchone()
        return total, qtd

    def totais_por_categoria(self, mes):
        self.cursor.execute("SELECT categoria, SUM(valor) FROM gastos WHERE mes_ano = ? "
                            "GROUP BY categoria", (mes,))
        return self.cursor.fetchall()

    def atualizar_acumulado(self):
        """Mostra, enquanto você lança, quanto já gastou na categoria escolhida no mês."""
        try:
            mes = normalizar_mes(self.mes_gasto.get())
        except ValueError:
            self.label_acumulado.config(text="")
            return
        categoria = self.combo_categoria.get()
        total, qtd = self.total_gastos(mes, categoria or None)
        plural = "s" if qtd != 1 else ""
        if categoria:
            texto = f"Já gasto em {categoria} ({mes}): R$ {total:.2f} em {qtd} lançamento{plural}"
        else:
            texto = f"Total gasto em {mes}: R$ {total:.2f} em {qtd} lançamento{plural}"
        self.label_acumulado.config(text=texto)

    def atualizar_resumo(self):
        """Recalcula os totais do mês e redesenha o gráfico de pizza."""
        try:
            mes = normalizar_mes(self.mes_resumo.get())
        except ValueError:
            self.label_total_resumo.config(text="Mês/Ano inválido (use MM/AAAA)")
            self.label_renda_resumo.config(text="")
            self.canvas_pizza.delete("all")
            return

        totais = self.totais_por_categoria(mes)
        gasto_total = sum(valor for _, valor in totais)
        self.label_total_resumo.config(text=f"Total gasto em {mes}: R$ {gasto_total:.2f}")

        self.cursor.execute("SELECT valor FROM renda WHERE mes_ano = ?", (mes,))
        renda_resultado = self.cursor.fetchone()
        renda = renda_resultado[0] if renda_resultado else 0.0
        if renda > 0:
            self.label_renda_resumo.config(
                text=f"Renda: R$ {renda:.2f}  ·  gastos = {gasto_total / renda * 100:.1f}% da renda  ·  "
                     f"saldo: R$ {renda - gasto_total:.2f}")
        else:
            self.label_renda_resumo.config(text="Renda deste mês ainda não cadastrada")

        self.desenhar_pizza(totais, mes)

    def desenhar_pizza(self, totais, mes):
        c = self.canvas_pizza
        c.delete("all")
        largura = int(c.cget("width"))
        altura = int(c.cget("height"))

        fatias, legenda = montar_fatias(totais)
        total = sum(valor for _, valor, _ in legenda)
        if total <= 0:
            c.create_text(largura / 2, altura / 2, text=f"Nenhum gasto registrado em {mes}.",
                          fill=COR_TEXTO_SUAVE, font=("", 11))
            return

        # Pizza à esquerda
        raio = 105
        cx, cy = 20 + raio, 20 + raio
        caixa = (cx - raio, cy - raio, cx + raio, cy + raio)
        if len(fatias) == 1:
            # Um arco de 360° não aparece no Tk; uma categoria só vira um círculo inteiro
            c.create_oval(*caixa, fill=fatias[0][2], outline=COR_FUNDO_GRAFICO, width=2)
        else:
            inicio = 90  # começa no topo (12 horas) e segue no sentido horário
            for _, valor, cor in fatias:
                extensao = -360 * valor / total
                c.create_arc(*caixa, start=inicio, extent=extensao, fill=cor,
                             outline=COR_FUNDO_GRAFICO, width=2, style=tk.PIESLICE)
                inicio += extensao

        # Porcentagem dentro das fatias grandes o bastante para caber o texto
        inicio = 90
        for _, valor, cor in fatias:
            fracao = valor / total
            meio = math.radians(inicio - 180 * fracao)
            inicio -= 360 * fracao
            if fracao >= 0.06:
                distancia = 0 if fracao == 1 else raio * 0.62
                x = cx + distancia * math.cos(meio)
                y = cy - distancia * math.sin(meio)
                cor_texto = COR_TEXTO if cor in CORES_COM_TEXTO_ESCURO else "#ffffff"
                c.create_text(x, y, text=f"{fracao * 100:.0f}%", fill=cor_texto, font=("", 10, "bold"))

        if len(legenda) > len(CORES_PIZZA):
            c.create_text(cx, cy + raio + 28, text="Em cinza: categorias menores,\nsomadas numa fatia só",
                          justify=tk.CENTER, fill=COR_TEXTO_SUAVE, font=("", 9))

        # Legenda à direita: todas as categorias com o total acumulado no mês
        x0 = 2 * raio + 50
        col_valor = largura - 62
        col_pct = largura - 8
        y = 24
        c.create_text(x0, y, text="Categoria", anchor="w", fill=COR_TEXTO_SUAVE, font=("", 9))
        c.create_text(col_valor, y, text="Total", anchor="e", fill=COR_TEXTO_SUAVE, font=("", 9))
        c.create_text(col_pct, y, text="%", anchor="e", fill=COR_TEXTO_SUAVE, font=("", 9))
        y += 20
        for categoria, valor, cor in legenda:
            c.create_rectangle(x0, y - 6, x0 + 12, y + 6, fill=cor, outline=cor)
            c.create_text(x0 + 20, y, text=categoria, anchor="w", fill=COR_TEXTO, font=("", 9))
            c.create_text(col_valor, y, text=f"R$ {valor:.2f}", anchor="e", fill=COR_TEXTO, font=("", 9))
            c.create_text(col_pct, y, text=f"{valor / total * 100:.1f}%", anchor="e",
                          fill=COR_TEXTO_SUAVE, font=("", 9))
            y += 21

if __name__ == "__main__":
    root = tk.Tk()
    app = AppControleGastos(root)
    root.mainloop()

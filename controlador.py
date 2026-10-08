import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime

CATEGORIAS = [
    "20% guardar", "Condominio", "Aluguel", "Terapia", 
    "Agua e luz e Gás", "Internet", "Cursos Medicina", 
    "Restaurante/padaria", "IFOOD", "Mercado", "Uber", 
    "Combustível", "Farmácia/saúde", "Academia", 
    "Desejos e Mimos", "Lazer", "Descontos salário", 
    "Presentes/Inscrições", "Outros"
]

class AppControleGastos:
    def __init__(self, root):
        self.root = root
        self.root.title("Controle Financeiro")
        self.root.geometry("550x550")
        
        self.id_gasto_editando = None # Controle para saber se está editando
        
        self.conectar_db()
        self.criar_interface()
        self.atualizar_lista_gastos()

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

        ttk.Label(aba_gastos, text="Categoria:").pack(pady=(5, 0))
        self.combo_categoria = ttk.Combobox(aba_gastos, values=CATEGORIAS, state="readonly")
        self.combo_categoria.pack()

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

        # ================= ABA 2: Renda Mensal =================
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

        # ================= ABA 3: Relatório =================
        aba_relatorio = ttk.Frame(abas)
        abas.add(aba_relatorio, text="Relatório Mensal")

        ttk.Label(aba_relatorio, text="Mês/Ano para consulta:").pack(pady=5)
        self.mes_relatorio = ttk.Entry(aba_relatorio)
        self.mes_relatorio.insert(0, datetime.now().strftime("%m/%Y"))
        self.mes_relatorio.pack()

        ttk.Button(aba_relatorio, text="Gerar Relatório", command=self.gerar_relatorio).pack(pady=10)

        self.texto_relatorio = tk.Text(aba_relatorio, height=15, width=55, state="disabled")
        self.texto_relatorio.pack(pady=5)

        # ================= ABA 4: Configurações =================
        aba_config = ttk.Frame(abas)
        abas.add(aba_config, text="Configurações")
        
        ttk.Label(aba_config, text="Área de Risco", font=("", 12, "bold")).pack(pady=(30, 10))
        ttk.Label(aba_config, text="Essa opção apagará o banco de dados inteiro.\nUse apenas se quiser começar tudo do zero.").pack(pady=5)
        
        btn_apagar = tk.Button(aba_config, text="LIMPAR TODOS OS DADOS", bg="red", fg="white", command=self.limpar_dados)
        btn_apagar.pack(pady=20)

    # =============== FUNÇÕES ===============
    
    def salvar_gasto(self):
        mes = self.mes_gasto.get()
        categoria = self.combo_categoria.get()
        try:
            valor = float(self.valor_gasto.get().replace(',', '.'))
            if not categoria:
                raise ValueError("vazio")
            
            if self.id_gasto_editando:
                # Atualiza gasto existente
                self.cursor.execute("UPDATE gastos SET mes_ano=?, categoria=?, valor=? WHERE id=?", 
                                    (mes, categoria, valor, self.id_gasto_editando))
                self.mostrar_aviso(self.status_gasto, "Gasto atualizado!")
            else:
                # Cria um novo gasto
                self.cursor.execute("INSERT INTO gastos (mes_ano, categoria, valor) VALUES (?, ?, ?)", 
                                    (mes, categoria, valor))
                self.mostrar_aviso(self.status_gasto, "Gasto salvo!")
                
            self.conn.commit()
            self.limpar_campos_gasto()
            self.atualizar_lista_gastos()
            
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

    def excluir_gasto(self):
        if self.id_gasto_editando:
            self.cursor.execute("DELETE FROM gastos WHERE id=?", (self.id_gasto_editando,))
            self.conn.commit()
            self.limpar_campos_gasto()
            self.atualizar_lista_gastos()
            self.mostrar_aviso(self.status_gasto, "Gasto excluído!")

    def limpar_campos_gasto(self):
        self.id_gasto_editando = None
        self.valor_gasto.delete(0, tk.END)
        self.combo_categoria.set('')
        
        # Volta os botões pro modo normal
        self.btn_salvar.config(text="Registrar Novo")
        self.btn_cancelar_edicao.config(state=tk.DISABLED)
        self.btn_excluir.config(state=tk.DISABLED)

    def atualizar_lista_gastos(self):
        # Limpa a tabela
        for row in self.tree.get_children():
            self.tree.delete(row)
        # Busca os últimos cadastros
        self.cursor.execute("SELECT id, mes_ano, categoria, valor FROM gastos ORDER BY id DESC")
        for linha in self.cursor.fetchall():
            self.tree.insert('', tk.END, values=(linha[0], linha[1], linha[2], f"{linha[3]:.2f}"))

    def salvar_renda(self):
        mes = self.mes_renda.get()
        try:
            valor = float(self.valor_renda.get().replace(',', '.'))
            self.cursor.execute("REPLACE INTO renda (mes_ano, valor) VALUES (?, ?)", (mes, valor))
            self.conn.commit()
            self.mostrar_aviso(self.status_renda, "Renda salva com sucesso!")
        except ValueError:
            messagebox.showerror("Erro", "Insira um valor numérico válido.")

    def mostrar_aviso(self, label, texto):
        label.config(text=texto)
        # Apaga o texto depois de 2.5 segundos (2500 milissegundos)
        self.root.after(2500, lambda: label.config(text=""))

    def gerar_relatorio(self):
        mes = self.mes_relatorio.get()
        
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
            self.texto_relatorio.config(state="normal")
            self.texto_relatorio.delete("1.0", tk.END)
            self.texto_relatorio.config(state="disabled")
            messagebox.showinfo("Sucesso", "Todos os dados foram apagados permanentemente.")

if __name__ == "__main__":
    root = tk.Tk()
    app = AppControleGastos(root)
    root.mainloop()

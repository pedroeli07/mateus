import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from fpdf import FPDF
import streamlit as st
import tempfile
from datetime import datetime, timedelta

# Inicialize st.session_state se ainda não estiver definido
if 'data_desejada' not in st.session_state:
    st.session_state.data_desejada = datetime(2000, 1, 1)
if 'numero_instalacao' not in st.session_state:
    st.session_state.numero_instalacao = []
    
def process_data(df, data_desejada, numero_instalacao):
   # df['Período'] = pd.to_datetime(df['Período'], format='%m/%y', errors='coerce')
   #df.dropna(subset=['Período'], inplace=True)  # Drop rows with invalid dates

    # Filtrar o DataFrame com base na data e nos números de instalação fornecidos pelo usuário
    df_filtered = df[(df['Período'] == data_desejada) & (df['Instalação'].isin(numero_instalacao))]

    # Remover as colunas indesejadas
    df_filtered = df_filtered[df_filtered['Compensação'] != 0]

    # Mapear a modalidade com base no número de instalação
    df_filtered.loc[df_filtered['Instalação'] == '3013110767', 'Modalidade'] = 'GBBH - Lj 02'
    df_filtered.loc[df_filtered['Instalação'] == '3013096188', 'Modalidade'] = 'GBBH - Lj 01'

    # Arredondar o saldo atual para duas casas decimais
    df_filtered['Saldo Atual'] = df_filtered['Saldo Atual'].round(2)
    
    # Obtém o último período após o filtro e formata para 'mm/yy'
    mes_periodo = df_filtered['Período'].iloc[0]
    return df_filtered, mes_periodo


# Função para calcular consumo e energia injetada por mês
def calculate_consumption_generation(df_copy):
    df_copy['Período'] = pd.to_datetime(df_copy['Período'], format='%m/%Y', errors='coerce')
    df_copy.dropna(subset=['Período'], inplace=True)  # Drop rows with invalid dates

    monthly_data = df_copy.groupby('Período').agg({'Consumo': 'sum', 'Geração': lambda x: x[x != 0].sum()})
    
    months_map = {
        'Jan': 'Jan/', 'Feb': 'Fev/', 'Mar': 'Mar/', 'Apr': 'Abr/', 'May': 'Mai/', 'Jun': 'Jun/',
        'Jul': 'Jul/', 'Aug': 'Ago/', 'Sep': 'Set/', 'Oct': 'Out/', 'Nov': 'Nov/', 'Dec': 'Dez/'
    }
    monthly_data.index = (monthly_data.index - pd.DateOffset(months=1)).strftime('%b-%y')
    monthly_data.index = monthly_data.index.map(lambda x: x.capitalize())
    monthly_data.index = monthly_data.index.map(lambda x: months_map[x.split('-')[0]] + x.split('-')[1])
    
    monthly_data = monthly_data.rename(columns={'Consumo': 'Consumo [kWh]', 'Geração': 'Energia Injetada [kWh]'})
    
    average_consumption = monthly_data['Consumo [kWh]'].mean()
    average_generation = monthly_data['Energia Injetada [kWh]'].mean()
    
    monthly_data.loc['Média'] = [int(average_consumption), int(average_generation)]
    monthly_data.reset_index(inplace=True)

    return monthly_data


def generate_image(preprocessed_df, monthly_data, RECEBIDO, VALOR_A_PAGAR, data_desejada, economia, cliente_text):
    img = Image.open('boleto_padrao02.png')
    draw = ImageDraw.Draw(img)
    
    recebido_text = str(int(RECEBIDO))
    valor_a_pagar_text = str(VALOR_A_PAGAR)
    
    mes_text = str(data_desejada.strftime("%m/%y"))
    vencimento_text = "26/" + data_desejada.strftime("%m/%y")

    economia_formatada = "{:.2f}".format(economia)
    economia_text = economia_formatada.replace('.', ',')
    
    font_bold1 = ImageFont.truetype("OpenSans-Bold.ttf", size=38)
    font_regular1 = ImageFont.truetype("OpenSans-Regular.ttf", size=25)

    draw.text((910, 1168), recebido_text, fill="black", font=font_bold1)
    draw.text((940, 1407), valor_a_pagar_text, fill="black", font=font_bold1)
    draw.text((297, 631), cliente_text, fill="black", font=font_regular1)
    draw.text((440, 667), mes_text, fill="black", font=font_regular1)
    draw.text((360, 702), vencimento_text, fill="black", font=font_regular1)
    draw.text((1060, 2207), economia_text, fill="black", font=font_bold1)

    # Selecionar apenas os últimos 11 meses com registro
    monthly_data01 = monthly_data.iloc[-12:]

    dataframe_position1 = (255, 1130)

    dataframe_position = (220, 868)
    
    font_bold_df = ImageFont.truetype("OpenSans-Bold.ttf", size=13)
    font_bold_dff = ImageFont.truetype("OpenSans-ExtraBold.ttf", size=13)
    font_df = ImageFont.truetype("OpenSans-Regular.ttf", size=13)

    color_light_gray = "#F0F0F0"
    color_dark_gray = "#D3D3D3"
    cell_width_df = 160
    cell_height_df = 28
    
    columns = list(monthly_data01.columns)
    for j, column_name in enumerate(columns):
        text_width = draw.textlength(str(column_name), font=font_bold_dff)
        text_position_x = dataframe_position1[0] + j * cell_width_df + (cell_width_df - text_width) // 2
        draw.rectangle(
            [(dataframe_position1[0] + j * cell_width_df, dataframe_position1[1]),
             (dataframe_position1[0] + (j + 1) * cell_width_df, dataframe_position1[1] + cell_height_df)],
            fill=color_dark_gray,
            outline="black"
        )
        draw.text((text_position_x, dataframe_position1[1] + 2), str(column_name), fill="black", font=font_bold_df)
    
    for i, (_, row) in enumerate(monthly_data01.iterrows()):
        for j, cell_value in enumerate(row):
            background_color_df = color_dark_gray if i == len(monthly_data01) - 1 else color_light_gray
            draw.rectangle(
                [(dataframe_position1[0] + j * cell_width_df, dataframe_position1[1] + (i + 1) * cell_height_df),
                 (dataframe_position1[0] + (j + 1) * cell_width_df, dataframe_position1[1] + (i + 2) * cell_height_df)],
                fill=background_color_df,
                outline="black"
            )
            cell_text = str(cell_value)
            if i == len(monthly_data01) - 1:
                cell_text = cell_text.upper() if columns[j] == "Período" else cell_text
                text_width = draw.textlength(cell_text, font=font_bold_df)
                text_font = font_bold_df
            else:
                text_width = draw.textlength(cell_text, font=font_df)
                text_font = font_df
            text_height = text_font.size
            text_position = (
                dataframe_position1[0] + j * cell_width_df + (cell_width_df - text_width) // 2,
                dataframe_position1[1] + (i + 1) * cell_height_df + (cell_height_df - text_height) // 2
            )
            draw.text(text_position, cell_text, fill="black", font=text_font)

    font_bold_df3 = ImageFont.truetype("OpenSans-Bold.ttf", size=18)
    font_df3 = ImageFont.truetype("OpenSans-Regular.ttf", size=18)
   
    cell_width_df = 180
    cell_height_df = 46
    
    
    preprocessed_df.drop(['Transferido', 'Geração'], axis=1, inplace=True)

  
    # Obter as colunas do preprocessed_df
    columns = list(preprocessed_df.columns)

    for j, column_name in enumerate(columns):
        text_width = draw.textlength(str(column_name), font=font_bold_df3)
        text_position_x = dataframe_position[0] + j * cell_width_df + (cell_width_df - text_width) // 2
        draw.rectangle(
            [(dataframe_position[0] + j * cell_width_df, dataframe_position[1]),
             (dataframe_position[0] + (j + 1) * cell_width_df, dataframe_position[1] + cell_height_df)],
            fill=color_dark_gray,
            outline="black"
        )
        draw.text((text_position_x, dataframe_position[1] + 10), str(column_name), fill="black", font=font_bold_df3)
    
    for i, (_, row) in enumerate(preprocessed_df.iterrows()):
        for j, cell_value in enumerate(row):
            background_color_df = color_light_gray if i % 2 == 0 else color_dark_gray
            draw.rectangle(
                [(dataframe_position[0] + j * cell_width_df, dataframe_position[1] + (i + 1) * cell_height_df),
                 (dataframe_position[0] + (j + 1) * cell_width_df, dataframe_position[1] + (i + 2) * cell_height_df)],
                fill=background_color_df,
                outline="black"
            )
            cell_text = str(cell_value)
            text_width = draw.textlength(cell_text, font=font_df3)
            text_height = font_df3.size
            text_position = (
                dataframe_position[0] + j * cell_width_df + (cell_width_df - text_width) // 2,
                dataframe_position[1] + (i + 1) * cell_height_df + (cell_height_df - text_height) // 2
            )
            draw.text(text_position, cell_text, fill="black", font=font_df3)

    return img

def generate_pdf(image):
    # Definir dimensões do PDF (8.28 x 11.69 inches em pontos)
    pdf = FPDF(unit='pt', format=[598.56, 845.28])
    pdf.add_page()
    
    # Salvar a imagem temporariamente em um arquivo
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
        image.save(tmpfile, format='PNG')
        tmpfile_path = tmpfile.name

    # Adicionar a imagem ao PDF
    pdf.image(tmpfile_path, x=0, y=0, w=598.56, h=845.28)

    # Salvar o PDF em um objeto BytesIO
    pdf_output = BytesIO()
    pdf.output(dest='S').encode('latin1')
    pdf_output.write(pdf.output(dest='S').encode('latin1'))
    pdf_output.seek(0)

    return pdf_output

# Aplicação Streamlit
st.title("Processamento de Dados de Energia")

uploaded_file = st.file_uploader("Escolha o arquivo CSV ou XLSX", type=["csv", "xlsx"])

if uploaded_file is not None:
    if uploaded_file.type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        df = pd.read_excel(uploaded_file)
    else:
        # Ler o arquivo CSV e forçar a coluna de instalação a ser tratada como string
        df = pd.read_csv(uploaded_file, delimiter=";", decimal=",", encoding="latin1", dtype={"Instalação": str})
   
    
    # Remover formatação indesejada da coluna de instalação
    df['Instalação'] = df['Instalação'].astype(str).str.replace(',', '')

    # Exibir o DataFrame sem formatação automática dos números
    st.write(df)
           
            # Remover as colunas indesejadas
    cols_to_drop = ["Quantidade Saldo a Expirar", "Período Saldo a Expirar", "Quota",
                    "Posto Horário", "Saldo Anterior", "Saldo Expirado"]
    
    df = df.drop(columns=cols_to_drop)
    df_copy = df.copy()
    df_copy2 = df.copy()
   
   
    # Exibir as datas únicas disponíveis na coluna 'Período'
    available_dates = df['Período'].unique()
    data_desejada = st.selectbox("Selecione a data desejada:", available_dates, index=0, key="data_desejada_selectbox")

    # Se a data selecionada for None, significa que nenhuma data foi selecionada ainda
    if data_desejada is not None:
        # Extraia o mês e o ano da data selecionada para usar nas operações
        selected_month, selected_year = data_desejada.split('/')
        selected_month = int(selected_month)
        selected_year = int(selected_year)
   
       # Exibir as datas únicas disponíveis na coluna 'Período'
    available_inst = df['Instalação'].unique()
    numero_instalacao = st.multiselect("Selecione o número de instalação desejado:", available_inst, key="numero_instalacao_selectbox")



    # Se a data selecionada for None, significa que nenhuma data foi selecionada ainda
    if numero_instalacao is not None:
        # Extraia o mês e o ano da data selecionada para usar nas operações
        selected_ins = numero_instalacao


    if st.button('Confirmar Período e Instalação'):
        st.session_state.data_desejada = data_desejada
        st.session_state.numero_instalacao = numero_instalacao

        st.success('Período e número de instalação confirmados!')

    if 'numero_instalacao' in st.session_state and 'data_desejada' in st.session_state :
        st.write(f"Período Referência selecionado : {st.session_state.data_desejada}")
        st.write(f"Número de instalação desejado: {st.session_state.numero_instalacao}")


    VALOR_KWH_CEMIG = st.slider("Digite o valor do KWh da Cemig (R$):", min_value=0.9000, max_value=1.00, value=0.900, step=0.001, format="%.3f")
    VALOR_KWH_CEMIG = st.number_input("Digite o valor do KWh da Cemig (R$):", min_value=0.900, max_value=1.00, value=VALOR_KWH_CEMIG, step=0.001, format="%.3f")

    DESCONTO = st.slider("Digite o valor do desconto (%):", min_value=10.0, max_value=35.0, value=20.0, step=0.01, format="%.2f")
    DESCONTO = st.number_input("Digite o valor do desconto (%):", min_value=10.0, max_value=35.0, value=DESCONTO, step=0.01, format="%.2f")

    VALOR_KWH_FATURADO = st.slider("Digite o valor do KWh faturado (R$):", min_value=0.7000, max_value=0.800, value=0.700, step=0.001, format="%.3f")
    VALOR_KWH_FATURADO = st.number_input("Digite o valor do KWh faturado (R$):", min_value=0.700, max_value=0.800, value=VALOR_KWH_FATURADO, step=0.001, format="%.3f")


    if st.button('Confirmar Valores'):
        st.session_state.VALOR_KWH_CEMIG = VALOR_KWH_CEMIG
        st.session_state.DESCONTO = DESCONTO
        st.session_state.VALOR_KWH_FATURADO = VALOR_KWH_FATURADO
        st.success('Valores confirmados!')

    if 'VALOR_KWH_CEMIG' in st.session_state and 'DESCONTO' in st.session_state and 'VALOR_KWH_FATURADO' in st.session_state:
        st.write(f"Valor KWh Cemig confirmado: R${st.session_state.VALOR_KWH_CEMIG}")
        st.write(f"Desconto confirmado: {st.session_state.DESCONTO}%")
        st.write(f"Valor KWh faturado confirmado: R${st.session_state.VALOR_KWH_FATURADO}")
        RECEBIDO = df['Transferido'].iloc[0] if not df.empty else 0
        VALOR_A_PAGAR = (RECEBIDO * VALOR_KWH_FATURADO).round(2)
       
        df_last_month, ultimo_periodo = process_data(df, st.session_state.data_desejada, st.session_state.numero_instalacao)
      
        st.write("Dados do último mês processados:")
        st.dataframe(df_last_month)

        st.write(f"Valor Recebido: R$ {RECEBIDO}")
        st.write(f"Valor a Pagar: R$ {VALOR_A_PAGAR}")

        monthly_data = calculate_consumption_generation(df_copy)
        st.write("Consumo e geração mensal:")
        st.dataframe(monthly_data)

        economia = RECEBIDO * (st.session_state.VALOR_KWH_CEMIG * (st.session_state.DESCONTO / 100))

        cliente_text = st.text_input("Digite o nome do cliente:", placeholder="Gracie Barra BH")
        if st.button('Confirmar Cliente'):
            st.session_state.cliente_text = cliente_text
            st.success('Cliente confirmado!')

        # Assuming ultimo_periodo might contain extra data
        if len(ultimo_periodo) > 5:  # Check if string length is greater than expected format
            ultimo_periodo = ultimo_periodo[:5]  # Slice the string to remove extra characters
            ultimo_periodo = datetime.strptime(ultimo_periodo, '%m/%y')
                
        # Agora você pode usar ultimo_periodo onde for necessário
        img = generate_image(df_last_month, monthly_data, RECEBIDO, VALOR_A_PAGAR, ultimo_periodo, economia, cliente_text)

        st.image(img, caption="Imagem gerada")

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        st.download_button(label="Baixar Imagem", data=buffer, file_name="imagem_processada.png", mime="image/png")

    

        # Inicializar o objeto ImageDraw para desenhar na imagem
        draw = ImageDraw.Draw(img)

        # Carregar as imagens do QR Code e do código de barras
        qr_code_image_file = st.file_uploader("Upload Imagem QR Code", type=["png", "jpeg"])
        barcode_image_file = st.file_uploader("Upload Imagem Código de Barras", type=["png", "jpeg"])

        if qr_code_image_file and barcode_image_file:
            qr_code_image = Image.open(qr_code_image_file)
            barcode_image = Image.open(barcode_image_file)

            # Redimensionar as imagens proporcionalmente para se ajustarem melhor ao boleto
            proporcao_qr_code = 285 / max(qr_code_image.width, qr_code_image.height)
            proporcao_codigo_barras = 1250 / max(barcode_image.width, barcode_image.height)

            qr_code_image = qr_code_image.resize((int(qr_code_image.width * proporcao_qr_code), int(qr_code_image.height * proporcao_qr_code)))
            barcode_image = barcode_image.resize((int(barcode_image.width * proporcao_codigo_barras), int(barcode_image.height * proporcao_codigo_barras)))

            # Definir as novas posições onde os QR Code e o código de barras serão colados na imagem do boleto
            posicao_x_qr_code = 1205
            posicao_y_qr_code = 1200
            posicao_x_codigo_barras = 225
            posicao_y_codigo_barras = 1600

            # Colar as imagens do QR Code e do código de barras na imagem do boleto
            img.paste(qr_code_image, (posicao_x_qr_code, posicao_y_qr_code))
            img.paste(barcode_image, (posicao_x_codigo_barras, posicao_y_codigo_barras))

            # Salvar a imagem final com os QR Code e código de barras adicionados
            img.save('boleto_com_qrcode01.png')

            #Create buttons for image and PDF generation
            generate_image_button = st.button("Gerar Imagem")
            generate_pdf_button = st.button("Gerar PDF")

            if generate_image_button:
                st.image(img, caption='Imagem Gerada', use_column_width=True)
            if generate_pdf_button:
                # Gerar o PDF e exibir o link para download
                pdf_output = generate_pdf(img)
                st.download_button(label="Baixar PDF", data=pdf_output, file_name=f"{cliente_text}{VALOR_A_PAGAR}.pdf", mime="application/pdf")




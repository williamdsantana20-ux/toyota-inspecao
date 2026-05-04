import cgi
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO

from PIL import Image, ImageOps


LIMITE_AREA_CLARA_NOK = 0.745
TAMANHO_DETECCAO = 640
TAMANHO_ANALISE = 128

HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Classificador de Pecas</title>
  <style>
    body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f4f6f8;color:#17202a;font-family:Arial,Helvetica,sans-serif;padding:24px;box-sizing:border-box}
    main{width:min(720px,100%);background:#fff;border:1px solid #d8dee6;border-radius:8px;padding:24px;box-sizing:border-box;box-shadow:0 8px 28px rgba(20,30,40,.08)}
    h1{margin:0 0 8px;font-size:24px}.meta{margin:0 0 20px;color:#52616f;font-size:14px}form{display:grid;gap:16px}
    input[type=file]{width:100%;padding:14px;border:1px dashed #8c9aaa;border-radius:8px;background:#f9fbfd;box-sizing:border-box}
    button{border:0;border-radius:8px;background:#1262b3;color:white;min-height:48px;font-size:16px;font-weight:700;cursor:pointer}button:disabled{background:#8c9aaa;cursor:wait}
    .resultado{margin-top:20px;border-radius:8px;padding:18px;border:1px solid #d8dee6;display:none}.resultado.ok{display:block;background:#edf8f0;border-color:#8fd19e}.resultado.nok{display:block;background:#fff0f0;border-color:#ee9b9b}
    .status{font-size:34px;font-weight:800;margin:0 0 8px}.detalhe{margin:0;color:#334155;line-height:1.5}img{width:100%;max-height:360px;object-fit:contain;border-radius:8px;margin-top:16px;background:#eef2f6}
  </style>
</head>
<body>
  <main>
    <h1>Classificador de Pecas</h1>
    <p class="meta">Envie ou tire uma foto da peca para verificar se ela parece OK ou NOK.</p>
    <form id="form">
      <input id="foto" name="foto" type="file" accept="image/*" capture="environment" required>
      <button id="botao" type="submit">Classificar peca</button>
    </form>
    <section id="resultado" class="resultado">
      <p id="status" class="status"></p>
      <p id="detalhe" class="detalhe"></p>
      <img id="preview" alt="Foto enviada">
    </section>
  </main>
  <script>
    const form=document.getElementById('form'),foto=document.getElementById('foto'),botao=document.getElementById('botao'),resultado=document.getElementById('resultado'),statusEl=document.getElementById('status'),detalhe=document.getElementById('detalhe'),preview=document.getElementById('preview');
    form.addEventListener('submit',async(e)=>{e.preventDefault();if(!foto.files.length)return;botao.disabled=true;botao.textContent='Analisando...';resultado.className='resultado';const dados=new FormData();dados.append('foto',foto.files[0]);try{const resp=await fetch('/classificar',{method:'POST',body:dados});const j=await resp.json();if(!resp.ok)throw new Error(j.erro||'Falha ao classificar');resultado.className='resultado '+(j.status==='OK'?'ok':'nok');statusEl.textContent=j.status;detalhe.textContent=`Confianca: ${j.confianca}. Area clara: ${j.area_clara}. Limite NOK: ${j.limite_nok}.`;preview.src=URL.createObjectURL(foto.files[0]);}catch(err){resultado.className='resultado nok';statusEl.textContent='ERRO';detalhe.textContent=err.message;preview.removeAttribute('src');}finally{botao.disabled=false;botao.textContent='Classificar peca';}});
  </script>
</body>
</html>"""


def abrir_imagem(origem):
    imagem = Image.open(origem)
    imagem.draft("RGB", (TAMANHO_DETECCAO, TAMANHO_DETECCAO))
    imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    return recortar_peca(imagem)


def recortar_peca(imagem):
    largura_original, altura_original = imagem.size
    det = imagem.copy()
    det.thumbnail((TAMANHO_DETECCAO, TAMANHO_DETECCAO))
    cinza = det.convert("L")
    pixels = list(cinza.getdata())
    xs = []
    ys = []
    w, h = cinza.size
    for y in range(h):
        linha = y * w
        for x in range(w):
            if pixels[linha + x] < 185:
                xs.append(x)
                ys.append(y)
    if len(xs) < 50:
        return imagem
    margem_x = max(10, int((max(xs) - min(xs)) * 0.18))
    margem_y = max(10, int((max(ys) - min(ys)) * 0.18))
    x1 = max(min(xs) - margem_x, 0)
    y1 = max(min(ys) - margem_y, 0)
    x2 = min(max(xs) + margem_x, w - 1)
    y2 = min(max(ys) + margem_y, h - 1)
    escala_x = largura_original / w
    escala_y = altura_original / h
    return imagem.crop((int(x1 * escala_x), int(y1 * escala_y), int((x2 + 1) * escala_x), int((y2 + 1) * escala_y)))


def otsu(valores):
    hist = [0] * 128
    for valor in valores:
        idx = max(0, min(127, int(valor / 256 * 128)))
        hist[idx] += 1
    total = sum(hist)
    soma_total = sum(i * c for i, c in enumerate(hist))
    cont = 0
    soma = 0
    melhor = 0
    melhor_var = -1
    for i, c in enumerate(hist):
        cont += c
        soma += i * c
        resto = total - cont
        if cont == 0 or resto == 0:
            continue
        var = ((soma_total * cont - soma * total) ** 2) / (cont * resto)
        if var > melhor_var:
            melhor_var = var
            melhor = i
    return melhor / 127 * 255


def medir_area_clara(origem):
    imagem = abrir_imagem(origem)
    imagem.thumbnail((TAMANHO_ANALISE, TAMANHO_ANALISE))
    fundo = Image.new("RGB", (TAMANHO_ANALISE, TAMANHO_ANALISE), (245, 245, 245))
    fundo.paste(imagem, ((TAMANHO_ANALISE - imagem.width) // 2, (TAMANHO_ANALISE - imagem.height) // 2))
    cinza = fundo.convert("L")
    valores = [v for v in cinza.getdata() if v < 237]
    if len(valores) < 100:
        valores = list(cinza.getdata())
    limite = otsu(valores)
    claros = sum(1 for v in valores if v > limite)
    return claros / len(valores)


def classificar(origem):
    area = medir_area_clara(origem)
    status = "NOK" if area >= LIMITE_AREA_CLARA_NOK else "OK"
    confianca = min(0.99, 0.50 + abs(area - LIMITE_AREA_CLARA_NOK) * 3.0)
    return {
        "status": status,
        "confianca": f"{confianca * 100:.1f}%",
        "area_clara": f"{area * 100:.1f}%",
        "limite_nok": f"{LIMITE_AREA_CLARA_NOK * 100:.1f}%",
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in {"/", "/index.html"}:
            self.enviar(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/status":
            self.enviar_json(200, {"ok": True})
            return
        self.enviar(404, b"Nao encontrado", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/classificar":
            self.enviar_json(404, {"erro": "Rota nao encontrada"})
            return
        tipo, _ = cgi.parse_header(self.headers.get("content-type", ""))
        if tipo != "multipart/form-data":
            self.enviar_json(400, {"erro": "Envie uma foto pelo formulario."})
            return
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("content-type")})
        campo = form["foto"] if "foto" in form else None
        if campo is None or not getattr(campo, "file", None):
            self.enviar_json(400, {"erro": "Nenhuma foto recebida."})
            return
        try:
            resultado = classificar(BytesIO(campo.file.read()))
        except Exception as erro:
            self.enviar_json(400, {"erro": f"Nao foi possivel ler a imagem: {erro}"})
            return
        self.enviar_json(200, resultado)

    def enviar_json(self, status, payload):
        self.enviar(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def enviar(self, status, conteudo, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(conteudo)))
        self.end_headers()
        self.wfile.write(conteudo)


def main():
    porta = int(os.environ.get("PORT", "8000"))
    servidor = ThreadingHTTPServer(("0.0.0.0", porta), Handler)
    print(f"Servidor iniciado na porta {porta}")
    servidor.serve_forever()


if __name__ == "__main__":
    main()

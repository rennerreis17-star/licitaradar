# LicitaRadar

Painel de licitações públicas (Lei 14.133/2021): cadastro da empresa pelo CNPJ (dados abertos da Receita Federal), radar de licitações abertas no PNCP em todo o Brasil, checagem de enquadramento, análise de edital para impugnação e análise de concorrentes para recurso.

## Como funciona

- **Site:** `index.html`, publicado no GitHub Pages.
- **Base de licitações:** o GitHub Actions (`.github/workflows/atualizar.yml`) roda `scripts/coletar_pncp.py` 3 vezes ao dia (6h, 12h e 18h, horário de Brasília). Ele baixa as licitações com propostas abertas no PNCP e grava em `data/`.
- **CNPJ:** consultado na hora pelo navegador (BrasilAPI → Minha Receita → CNPJ.ws).
- **Seus dados** (empresa, licitações salvas, concorrentes) ficam **só no navegador** de quem usa. Nada disso vai para o repositório. Faça backup em *Configurações*.

## Ativar (uma vez só)

1. Em **Settings → Pages**, em *Build and deployment → Source*, escolha **GitHub Actions**.
2. Em **Actions**, abra *Atualizar licitações e publicar* e clique em **Run workflow**.
3. Depois de uns minutos, o site fica em `https://<seu-usuario>.github.io/licitaradar/`.

## Ajustes

No arquivo `.github/workflows/atualizar.yml`:
- `DIAS`: quantos dias à frente buscar encerramentos (padrão 60).
- `MINUTOS`: tempo máximo da coleta de licitações (padrão 38).
- `MINUTOS_CONTRATOS`: tempo máximo da coleta de contratos para a página Mercado (padrão 18).
- Para mudar as modalidades, adicione `MODALIDADES: "6,8,4"` (6 Pregão Eletrônico, 8 Dispensa, 4 Concorrência Eletrônica, 7 Pregão Presencial, 5 Concorrência Presencial, 12 Credenciamento).

> As minutas geradas pela IA devem ser revisadas por advogado ou pelo responsável antes do protocolo.

"""Plain Portuguese assistance for Universal Remote users.

Pure logic, no network, no shell, no automatic changes and no sensitive logs.
Every reported issue offers a safe next step without technical jargon.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Guidance:
    code: str
    title: str
    explanation: str
    steps: tuple[str, ...]
    severity: str = "warning"
    page: str | None = None
    button: str = ""


MESSAGES: dict[str, Guidance] = {
    "LOCAL_OK": Guidance(
        "LOCAL_OK", "O programa está pronto para começar",
        "Os componentes locais parecem disponíveis. Isto não confirma uma ligação remota ao ChatGPT.",
        ("Abre Ligações para veres as opções de associação.",
         "Quando o outro serviço confirmar a ligação, podes começar a utilizá-lo."),
        "info", "Conexões", "Abrir ligações"),
    "INSTALL_INCOMPLETE": Guidance(
        "INSTALL_INCOMPLETE", "Faltam ficheiros do Universal Remote",
        "Alguns componentes necessários não foram encontrados. É normalmente possível reparar a instalação.",
        ("Fecha o Universal Remote.",
         "Abre novamente o instalador da mesma versão, obtido de uma fonte em que confies.",
         "Escolhe Reparar, se essa opção estiver disponível.",
         "Volta a abrir a aplicação e carrega em Verificar novamente."),
        "error"),
    "AGENT_MISSING": Guidance(
        "AGENT_MISSING", "Não foi encontrado o motor de ligação",
        "A interface abre, mas o componente responsável pela comunicação com as IAs está em falta.",
        ("Fecha a aplicação e executa o instalador original de uma fonte de confiança.",
         "Seleciona Reparar e abre novamente o Universal Remote.",
         "Se o antivírus apresentar um alerta, verifica a origem e o editor; não desatives a proteção."),
        "error"),
    "SETUP_INCOMPLETE": Guidance(
        "SETUP_INCOMPLETE", "Falta concluir a primeira configuração",
        "Ainda não existe uma pasta de trabalho autorizada para esta instalação.",
        ("Fecha e abre novamente a aplicação para retomar o assistente inicial.",
         "Escolhe uma pasta de trabalho e confirma as permissões que realmente pretendes usar.",
         "Se já concluíste o assistente, utiliza Verificar novamente."),
        "warning", "Início", "Voltar ao início"),
    "REMOTE_UNVERIFIED": Guidance(
        "REMOTE_UNVERIFIED", "Ligação remota ainda não confirmada",
        "Ter o motor instalado não significa que o ChatGPT já tenha acesso ao teu computador.",
        ("Abre Ligações para consultar o estado e os dispositivos associados.",
         "Confirma o pedido de ligação apenas se o reconheces.",
         "Se a ligação falhar, tenta novamente sem abrir portas do router nem desativar a firewall."),
        "info", "Conexões", "Abrir ligações"),
    "PAIRING_FAILED": Guidance(
        "PAIRING_FAILED", "Não foi possível associar o dispositivo",
        "A ligação não foi autorizada ou o pedido expirou. Nenhum acesso adicional deve ser concedido automaticamente.",
        ("Abre Ligações e escolhe Gerir dispositivos emparelhados.",
         "Inicia novamente o pedido no dispositivo que pretendes autorizar.",
         "Confirma que o identificador apresentado nos dois dispositivos é igual.",
         "Aprova apenas as permissões necessárias."),
        "warning", "Conexões", "Gerir ligações"),
    "PERMISSION_DENIED": Guidance(
        "PERMISSION_DENIED", "O Windows recusou esta operação",
        "A aplicação ou o dispositivo não tem autorização suficiente para concluir o pedido.",
        ("Abre Acesso e verifica as permissões atualmente autorizadas.",
         "Autoriza apenas a operação que reconheces, pelo tempo necessário.",
         "Não desatives o antivírus nem a firewall para contornar o aviso."),
        "warning", "Acesso", "Ver permissões"),
    "SECURITY_BLOCKED": Guidance(
        "SECURITY_BLOCKED", "A proteção do computador interrompeu a operação",
        "O Windows ou um programa de segurança poderá estar a bloquear o ficheiro ou a execução.",
        ("Lê o alerta e confirma o nome e a origem do ficheiro.",
         "Se não reconheces a origem, cancela a operação.",
         "Se é um instalador legítimo que escolheste executar, usa as opções de validação do próprio programa de segurança.",
         "Se continuar bloqueado, copia o resumo para pedir assistência sem enviar credenciais."),
        "warning"),
    "CONNECTION_FAILED": Guidance(
        "CONNECTION_FAILED", "Não foi possível estabelecer ligação",
        "O serviço de destino não respondeu ou a comunicação foi interrompida.",
        ("Confirma que tens ligação à Internet, caso uses um serviço remoto.",
         "Verifica se a aplicação do serviço está aberta e autenticada.",
         "Tenta ligar novamente e consulta Ligações se o problema continuar."),
        "warning", "Conexões", "Ver ligações"),
    "UPDATE_FAILED": Guidance(
        "UPDATE_FAILED", "A atualização não foi concluída",
        "A verificação de segurança ou a instalação pode ter recusado a nova versão.",
        ("Continua a usar a versão anterior se estiver a funcionar.",
         "Não instales manualmente pacotes de origem desconhecida.",
         "Volta a verificar mais tarde ou utiliza o instalador oficial.",
         "Se necessário, envia apenas o código do erro ao suporte, sem chaves nem palavras-passe."),
        "warning"),
    "TASK_FAILED": Guidance(
        "TASK_FAILED", "Não foi possível concluir a tarefa",
        "A operação terminou com erro ou deixou de responder.",
        ("Abre Tarefas para verificar se ainda está ativa.",
         "Consulta a saída apenas se não contiver dados pessoais.",
         "Se for seguro, repete apenas essa tarefa, sem reiniciar todas as restantes."),
        "warning", "Tarefas", "Ver tarefas"),
    "OPTIONAL_POWERSHELL": Guidance(
        "OPTIONAL_POWERSHELL", "A ferramenta avançada ainda não está disponível",
        "A aplicação continua a funcionar; apenas algumas funções opcionais podem precisar de PowerShell.",
        ("Abre Ligações e escolhe Verificar ou atualizar PowerShell.",
         "Confirma o download apenas se reconheceres a origem oficial da Microsoft.",
         "Se não usares comandos ou diagnósticos avançados, podes ignorar este aviso."),
        "info", "Conexões", "Ver opções"),
    "STARTUP_FAILED": Guidance(
        "STARTUP_FAILED", "O Universal Remote não conseguiu iniciar",
        "Ocorreu um problema ao carregar a aplicação. A tua configuração não precisa de ser apagada.",
        ("Fecha a janela e tenta abrir novamente o programa.",
         "Se continuar, executa Reparar através do instalador obtido de uma fonte de confiança.",
         "Se o problema persistir, comunica o tipo e o código do erro ao suporte."),
        "error"),
    "UNKNOWN_ERROR": Guidance(
        "UNKNOWN_ERROR", "Não conseguimos concluir esta operação",
        "Ocorreu um problema inesperado. Não precisas de saber programação para o resolver.",
        ("Tenta novamente uma única vez.",
         "Se continuar a falhar, abre Ajuda e executa Verificar novamente.",
         "Copia o resumo do diagnóstico, sem partilhar ficheiros, palavras-passe ou chaves."),
        "warning", "Ajuda", "Abrir ajuda"),
}


def guidance(code: str) -> Guidance:
    """Never display raw exception strings, paths, credentials or stack traces."""
    return MESSAGES.get(code, MESSAGES["UNKNOWN_ERROR"])


def diagnose(readiness: Iterable[object], local_agent: bool) -> tuple[Guidance, ...]:
    """Read-only checks: no false claims about live remote tunnel availability."""
    items = {getattr(row, "key", ""): row for row in readiness}
    issues: list[Guidance] = []
    if getattr(items.get("runtime"), "ok", True) is False:
        issues.append(guidance("INSTALL_INCOMPLETE"))
    if not local_agent or getattr(items.get("agent"), "ok", True) is False:
        issues.append(guidance("AGENT_MISSING"))
    if getattr(items.get("config"), "ok", True) is False:
        issues.append(guidance("SETUP_INCOMPLETE"))
    if issues:
        return tuple(issues)
    return (guidance("LOCAL_OK"), guidance("REMOTE_UNVERIFIED"))


def issue_for_exception(exc: BaseException, *, context: str = "") -> Guidance:
    if context == "startup":
        return guidance("STARTUP_FAILED")
    if context == "powershell":
        return guidance("OPTIONAL_POWERSHELL")
    if context == "pairing":
        return guidance("PAIRING_FAILED")
    if context == "permissions":
        return guidance("PERMISSION_DENIED")
    if context == "installation":
        return guidance("AGENT_MISSING")
    if context == "update":
        return guidance("UPDATE_FAILED")
    if context == "task":
        return guidance("TASK_FAILED")
    if isinstance(exc, PermissionError):
        return guidance("PERMISSION_DENIED")
    if isinstance(exc, FileNotFoundError):
        return guidance("INSTALL_INCOMPLETE")
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return guidance("CONNECTION_FAILED")
    return guidance("UNKNOWN_ERROR")


def friendly_text(item: Guidance) -> str:
    lines = [item.explanation, "", "O que fazer:"]
    lines.extend(f"{index}. {step}" for index, step in enumerate(item.steps, 1))
    return "\n".join(lines)


def safe_diagnostic_report(issues: Iterable[Guidance]) -> str:
    """Plain-text clipboard summary: never capture paths, names or exception args."""
    return ("Universal Remote — resumo de diagnóstico\n"
            "Este resumo não contém palavras-passe, caminhos pessoais ou chaves.\n"
            + "\n".join(f"{item.code}: {item.title}" for item in issues))

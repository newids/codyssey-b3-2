"""사용자에게 보여 줄 메시지를 가진 예외들."""


class AiGitgenError(Exception):
    """도구가 처리하는 모든 오류의 기반. 메시지는 그대로 터미널에 출력된다."""


class ConfigurationError(AiGitgenError):
    """실행 전에 고쳐야 하는 설정·사용법 오류. 종료 코드 2 (argparse 의 사용법 오류와 같은 값)."""


class UsageError(ConfigurationError):
    """옵션 값이 범위를 벗어나거나 함께 쓸 수 없는 옵션을 같이 줬다."""


class MissingApiKeyError(ConfigurationError):
    """API 키 환경변수가 없다. git 수집이나 API 호출 전에 확인한다."""


class AIRequestError(AiGitgenError):
    """AI API 호출 실패. HTTP 상태와 원인을 메시지에 담는다."""


class UnsupportedParameterError(AIRequestError):
    """모델이 특정 파라미터(예: temperature)를 거부했다."""

    def __init__(self, model: str, parameter: str, reason: str) -> None:
        super().__init__(f"'{model}' 모델은 {parameter} 를 지원하지 않습니다: {reason}")
        self.model = model
        self.parameter = parameter
        self.reason = reason


class RegistryError(AiGitgenError):
    """모델 레지스트리 파일을 읽거나 쓸 수 없다."""


class GitCommandError(AiGitgenError):
    """git 명령 실행 실패."""


class NotGitRepositoryError(GitCommandError):
    """Git 저장소 루트가 아니다."""


class OutputParseError(AiGitgenError):
    """모델 출력에서 제목을 찾을 수 없다."""


class ConventionError(ConfigurationError):
    """컨벤션 설정 파일(.ai-gitgen.json)을 읽을 수 없거나 값이 규격에 맞지 않는다."""


class MaskTimeoutError(AiGitgenError):
    """사용자 정의 마스킹 정규식이 제한 시간 안에 끝나지 않았다 (catastrophic backtracking 의심)."""

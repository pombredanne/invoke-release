__all__ = (
    'ConfigError',
    'ReleaseExit',
    'ReleaseFailure',
    'SourceControlError',
    'VersionError',
)


class ConfigError(Exception):
    """
    Exception raised when something is wrong with the Invoke Release configuration.
    """


class ReleaseExit(Exception):
    """
    Control-flow exception raised to cancel a release before changes are made.
    """


class ReleaseFailure(Exception):
    """
    Exception raised when something caused the release to fail, and cleanup is required.
    """


class SourceControlError(Exception):
    """
    Exception raised when a source control command unexpectedly fails.
    """


class VersionError(Exception):
    """
    Exception raised when there's a problem with a version.
    """

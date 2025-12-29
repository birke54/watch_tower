"""Ring connection manager for handling authentication and session management."""

import json
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

from ring_doorbell import Auth, Ring, Requires2FAError, RingDoorBell, AuthenticationError, RingError

from connection_managers.connection_manager_base import ConnectionManagerBase
from connection_managers.plugin_type import PluginType
from db.connection import get_database_connection
from db.cryptography.aes import decrypt
from db.models import VendorStatus as DBVendorStatus
from db.repositories.vendors_repository import VendorsRepository
from utils.logging_config import get_logger
from watch_tower.exceptions import RingConnectionManagerError
from watch_tower.registry.connection_manager_registry import (
    REGISTRY as connection_manager_registry,
    VendorStatus as RegistryVendorStatus,
)
from utils.metrics import MetricDataPointName
from utils.metric_helpers import inc_counter_metric

# Configure logger for this module
LOGGER = get_logger(__name__)


class RingConnectionManager(ConnectionManagerBase):
    """
    Manager for handling authentication and session management with the
    Ring API.
    """
    _user_agent: str = "WatchTower API"
    _plugin_type: PluginType = PluginType.RING
    _vendor_repository: VendorsRepository = VendorsRepository()

    def __init__(self) -> 'RingConnectionManager':
        """
        Implements the InterfaceConnectionManager interface for Ring cameras.
        """
        super().__init__()  # Call parent class's __init__
        self._plugin_type = PluginType.RING  # Set the plugin type
        self._ring: Optional[Ring] = None
        self._auth: Optional[Auth] = None
        self._is_authenticated: bool = False
        LOGGER.info("Created new RingConnectionManager instance")

    async def login(self) -> None:
        """
        Authenticates with the Ring API using token from database if available,
        otherwise performs a new authentication. Sets up the Ring session.
        Returns True if successful, False otherwise.
        """
        if self._is_authenticated:
            LOGGER.info("Already authenticated, skipping login")
            return

        LOGGER.info("Attempting to login with database token")
        _, session_factory = get_database_connection()
        with session_factory() as session:
            vendor = self._vendor_repository.get_by_field(
                session, 'plugin_type', self._plugin_type)
            success = False
            e = None
            try:
                # Try authentication with existing token first
                try:
                    if await self._authenticate_with_existing_token():
                        LOGGER.info("Successfully authenticated with existing token")
                        success = True
                except (AuthenticationError, RingError) as exc:
                    e = exc
                    LOGGER.error(
                        "Failed to authenticate with existing token: %s\n "
                        "Moving on to credential-based authentication", exc
                    )

                # Fall back to credential-based authentication
                if not success:
                    try:
                        if await self._authenticate_with_credentials(vendor):
                            # Update vendor status to active after successful auth
                            self._vendor_repository.update_status(
                                session, vendor.vendor_id, DBVendorStatus.ACTIVE)
                            LOGGER.info(
                                "Updated vendor status to active for %r",
                                self._plugin_type)
                            LOGGER.info("Successfully authenticated with credentials")
                            success = True
                    except (AuthenticationError, RingError) as exc:
                        e = exc
                        LOGGER.error(
                            "Failed to authenticate with credentials: %s", exc
                        )
            finally:
                if success:
                    inc_counter_metric(MetricDataPointName.RING_LOGIN_SUCCESS_COUNT)
                    LOGGER.info("Successfully authenticated with Ring")
                    return
                else:
                    inc_counter_metric(MetricDataPointName.RING_LOGIN_ERROR_COUNT)
                    if e is not None:
                        raise RingConnectionManagerError(f"Failed to authenticate with Ring: all authentication methods failed") from e
                    else:
                        raise RingConnectionManagerError(f"Failed to authenticate with Ring: all authentication methods failed")


    async def logout(self) -> bool:
        """
        Closes the Ring session and clears the authentication state.
        Returns True if successful, False otherwise.
        """
        if not self._is_authenticated:
            LOGGER.info("Not authenticated, skipping logout")
            return True

        LOGGER.info("Attempting to logout")
        self._ring = None
        self._auth = None
        self._is_authenticated = False
        inc_counter_metric(MetricDataPointName.RING_LOGOUT_SUCCESS_COUNT)
        LOGGER.info("Successfully logged out from Ring")
        return True

    def is_healthy(self) -> bool:
        """
        Checks if the Ring connection is healthy by verifying the authentication state.
        Returns True if authenticated, False otherwise.
        """
        try:
            if self._ring is None:
                return False
            self._ring.update_data()
            return True
        except Exception:
            return False

    async def get_cameras(self) -> Optional[Sequence[RingDoorBell]]:
        """
        Retrieves a list of Ring cameras associated with the authenticated account.
        Returns a list of camera IDs if successful, None if not authenticated.
        """
        if not self._is_authenticated:
            LOGGER.info("Not authenticated, cameras cannot be retrieved")
            return None

        try:
            if self._ring is None:
                return None
            self._ring.update_data()
            cameras = self._ring.video_devices()
            if cameras:
                LOGGER.info(
                    "Successfully retrieved %d cameras: %r",
                    len(cameras), cameras)
                return cameras
            LOGGER.info("No cameras found in response")
            return []
        except Exception as e:
            LOGGER.error("Error retrieving cameras: %s", e)
            LOGGER.exception("Full traceback:")
            return None

    def token_updated(self, token: Dict[str, Any],
                      vendor_id: Optional[int] = None) -> None:
        """Callback for when token is updated."""
        if vendor_id is None:
            LOGGER.error(
                "token_updated called without vendor_id - "
                "token may not be saved correctly")
            # Try to get vendor_id from database
            _, session_factory = get_database_connection()
            with session_factory() as session:
                vendor = self._vendor_repository.get_by_field(
                    session, 'plugin_type', self._plugin_type)
                if vendor:
                    vendor_id = vendor.vendor_id
                else:
                    LOGGER.error("Could not find vendor to update token")
                    return

        expire_dt = datetime.fromtimestamp(token['expires_at'])
        # Update in-memory registry
        registry_entry = connection_manager_registry.connection_managers[
            self._plugin_type]
        registry_entry['token'] = token
        registry_entry['expires_at'] = expire_dt

        # Update database
        _, session_factory = get_database_connection()
        with session_factory() as session:
            self._vendor_repository.update_token(
                session,
                vendor_id,
                json.dumps(token),
                expire_dt  # Pass datetime object, not string
            )
            inc_counter_metric(MetricDataPointName.RING_TOKEN_UPDATE_SUCCESS_COUNT)
            LOGGER.info(
                "Token updated in database for vendor_id: %d", vendor_id)
                

    @staticmethod
    def otp_callback() -> str:
        """
        Callback for 2FA code input. Prompts the user for a 2FA code.
        Returns the code as a string.
        """
        try:
            auth_code = input("2FA code: ")
            return auth_code
        except Exception as e:
            LOGGER.error("Failed to get 2FA code: %s", e)
            raise

    async def _authenticate_with_existing_token(self) -> bool:
        """Authenticate using an existing token from the database."""
        _, session_factory = get_database_connection()
        with session_factory() as session:
            vendor = self._vendor_repository.get_by_field(
                session, 'plugin_type', self._plugin_type)
            LOGGER.info("Found vendor in database: %r", vendor)
            if vendor and vendor.token:
                LOGGER.info("Loading token from database")
                # Convert memoryview or bytes to string before parsing JSON
                if hasattr(vendor.token, 'tobytes'):
                    token_str = vendor.token.tobytes().decode('utf-8')
                else:
                    # Already bytes, just decode
                    token_str = vendor.token.decode('utf-8')
                token = json.loads(token_str)
                LOGGER.info(
                    "Token expiration: %s, Current time: %s",
                    token['expires_at'], datetime.now().timestamp())
                if token:
                    # Create a lambda that captures vendor_id for the callback
                    def token_callback(token):
                        try:
                            return self.token_updated(token, vendor.vendor_id)
                        except DatabaseTransactionError as e:
                            raise

                    self._auth = Auth(
                        self._user_agent,
                        token,
                        token_callback  # Use lambda with vendor_id
                    )
                    self._ring = Ring(self._auth)
                    LOGGER.info("Created Ring object: %r", self._ring)
                    self._ring.create_session()
                    LOGGER.info("Created Ring session")
                    self._is_authenticated = True

                    # Update in-memory registry
                    registry_entry = (
                        connection_manager_registry.connection_managers[
                            self._plugin_type])
                    registry_entry['status'] = RegistryVendorStatus.ACTIVE
                    registry_entry['token'] = token
                    registry_entry['expires_at'] = datetime.fromtimestamp(
                        token['expires_at'])

                    LOGGER.info(
                        "Successfully connected to Ring using database token")
                    return True
                LOGGER.info("Existing token not found")
            else:
                LOGGER.info("No token found in database")
        return False

    async def _authenticate_with_credentials(self, vendor: Any) -> bool:
        """Authenticate using stored credentials."""
        LOGGER.info(
            "No valid or expired token found in database, "
            "performing new authentication")
        username = vendor.username
        password = decrypt(vendor.password_enc)
        self._auth = self.perform_auth(username, password, vendor.vendor_id)
        self._ring = Ring(self._auth)
        registry_entry = connection_manager_registry.connection_managers[
            self._plugin_type]
        registry_entry['status'] = RegistryVendorStatus.ACTIVE
        self._is_authenticated = True
        return True

    def perform_auth(self, username: str, password: str, vendor_id: int) -> Auth:
        """
        Performs authentication with the Ring API.
        Handles 2FA if required.
        Returns an Auth object if successful.
        """
        try:
            # Create a lambda that captures vendor_id for the callback
            def token_callback(token):
                return self.token_updated(token, vendor_id)

            auth = Auth(self._user_agent, None, token_callback)
            try:
                auth.fetch_token(username, password)
            except Requires2FAError:
                # If 2FA is required, prompt for code
                auth.fetch_token(username, password, self.otp_callback())
            LOGGER.info("Successfully connected to Ring using database token")
            return auth
        except (AuthenticationError, RingError) as e:
            LOGGER.error("Authentication failed: %s", e)
            raise RingConnectionManagerError(
                f"Authentication failed: {e}"
            ) from e

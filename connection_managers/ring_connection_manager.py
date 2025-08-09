import json
from typing import Any, Dict, Optional, Sequence

from watch_tower.exceptions import ConnectionManagerError
from watch_tower.registry.connection_manager_registry import registry, VendorStatus as RegistryVendorStatus
from connection_managers.plugin_type import PluginType
import logging
from ring_doorbell import Ring, Auth, Requires2FAError, RingDoorBell
from db.connection import get_database_connection
from db.models import VendorStatus as DBVendorStatus
from db.repositories.vendors_repository import VendorsRepository
from datetime import datetime
from db.cryptography.aes import decrypt

from connection_managers.connection_manager_base import ConnectionManagerBase

# Configure logger for this module
logger = logging.getLogger(__name__)


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
        logger.info("Created new RingConnectionManager instance")

    async def login(self) -> None:
        """
        Authenticates with the Ring API using token from database if available,
        otherwise performs a new authentication. Sets up the Ring session.
        Returns True if successful, False otherwise.
        """
        if self._is_authenticated:
            logger.info("Already authenticated, skipping login")

        logger.info("Attempting to login with database token")
        try:
            engine, session_factory = get_database_connection()
            with session_factory() as session:
                vendor = self._vendor_repository.get_by_field(
                    session, 'plugin_type', self._plugin_type)

                # Try authentication with existing token first
                try:
                    if await self._authenticate_with_existing_token():
                        return
                except Exception as e:
                    logger.error(
                        f"Failed to authenticate with existing token: {e}\n Moving on to credential-based authentication")

                # Fall back to credential-based authentication
                try:
                    if await self._authenticate_with_credentials(vendor):
                        # Update vendor status to active after successful authentication
                        self._vendor_repository.update_status(
                            session, vendor.vendor_id, DBVendorStatus.ACTIVE)
                        logger.info(
                            f"Updated vendor status to active for {self._plugin_type}")
                        return
                except Exception as e:
                    logger.error(
                        f"Failed to authenticate with credentials: {e}\n Moving on to new authentication")

            raise
        except Exception as e:
            logger.error(f"Failed to authenticate with Ring: {str(e)}")
            raise ConnectionManagerError(f"Failed to authenticate with Ring: {str(e)}")

    async def logout(self) -> bool:
        """
        Closes the Ring session and clears the authentication state.
        Returns True if successful, False otherwise.
        """
        if not self._is_authenticated:
            logger.info("Not authenticated, skipping logout")
            return True

        logger.info("Attempting to logout")
        self._ring = None
        self._auth = None
        self._is_authenticated = False
        logger.info("Successfully logged out from Ring")
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
        except Exception as e:
            return False

    async def get_cameras(self) -> Optional[Sequence[RingDoorBell]]:
        """
        Retrieves a list of Ring cameras associated with the authenticated account.
        Returns a list of camera IDs if successful, None if not authenticated.
        """
        if not self._is_authenticated:
            logger.info("Not authenticated, cameras cannot be retrieved")
            return None

        try:
            if self._ring is None:
                return None
            self._ring.update_data()
            cameras = self._ring.video_devices()
            if cameras:
                logger.info(f"Successfully retrieved {len(cameras)} cameras: {cameras}")
                return cameras
            else:
                logger.info("No cameras found in response")
                return []
        except Exception as e:
            logger.error(f"Error retrieving cameras: {e}")
            logger.exception("Full traceback:")
            return None

    def token_updated(self, token: Dict[str, Any],
                      vendor_id: Optional[int] = None) -> None:
        """Callback for when token is updated."""
        expire_dt = datetime.fromtimestamp(token['expires_at'])
        # Update in-memory registry
        registry.connection_managers[self._plugin_type]['token'] = token
        registry.connection_managers[self._plugin_type]['expires_at'] = expire_dt

        # Update database
        engine, session_factory = get_database_connection()
        with session_factory() as session:
            self._vendor_repository.update_token(
                session,
                vendor_id,
                json.dumps(token),
                expire_dt.isoformat()  # Convert datetime to ISO format string
            )

    def otp_callback(self) -> str:
        """
        Callback for 2FA code input. Prompts the user for a 2FA code.
        Returns the code as a string.
        """
        try:
            auth_code = input("2FA code: ")
            return auth_code
        except Exception as e:
            logger.error(f"Failed to get 2FA code: {e}")
            raise

    async def _authenticate_with_existing_token(self) -> bool:
        """Authenticate using an existing token from the database."""
        engine, session_factory = get_database_connection()
        with session_factory() as session:
            vendor = self._vendor_repository.get_by_field(
                session, 'plugin_type', self._plugin_type)
            logger.info(f"Found vendor in database: {vendor}")
            if vendor and vendor.token:
                logger.info("Loading token from database")
                # Convert memoryview to string before parsing JSON
                token_str = vendor.token.tobytes().decode('utf-8')
                token = json.loads(token_str)
                logger.info(
                    f"Token expiration: {token['expires_at']}, Current time: {datetime.now().timestamp()}")
                if token:
                    self._auth = Auth(
                        self._user_agent,
                        token,
                        self.token_updated
                    )
                    self._ring = Ring(self._auth)
                    logger.info(f"Created Ring object: {self._ring}")
                    self._ring.create_session()
                    logger.info("Created Ring session")
                    self._is_authenticated = True

                    # Update in-memory registry
                    registry.connection_managers[self._plugin_type]['status'] = RegistryVendorStatus.ACTIVE
                    registry.connection_managers[self._plugin_type]['token'] = token
                    registry.connection_managers[self._plugin_type]['expires_at'] = datetime.fromtimestamp(
                        token['expires_at'])

                    logger.info("Successfully connected to Ring using database token")
                    return True
                else:
                    logger.info("Existing token not found")
            else:
                logger.info("No token found in database")
        return False

    async def _authenticate_with_credentials(self, vendor: Any) -> bool:
        """Authenticate using stored credentials."""
        logger.info(
            "No valid or expired token found in database, performing new authentication")
        username = vendor.username
        password = decrypt(vendor.password_enc)
        self._auth = self.perform_auth(username, password, vendor.vendor_id)
        self._ring = Ring(self._auth)
        registry.connection_managers[self._plugin_type]['status'] = RegistryVendorStatus.ACTIVE
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
            def token_callback(token): return self.token_updated(token, vendor_id)
            auth = Auth(self._user_agent, None, token_callback)
            try:
                auth.fetch_token(username, password)
            except Requires2FAError:
                # If 2FA is required, prompt for code
                auth.fetch_token(username, password, self.otp_callback())
            logger.info("Successfully connected to Ring using database token")
            return auth
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise

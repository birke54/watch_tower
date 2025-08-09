'''
AES Cryptography Library

This module provides cryptographic functions for encryption and decryption using AES-256-CBC
with PBKDF2 key derivation and PKCS7 padding.
'''

import os
import base64
from typing import Union
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from aws.secrets_manager.secrets_manager_service import get_db_secret
from db.exceptions import CryptographyError
from watch_tower.config import config
from utils.logging_config import get_logger

logger = get_logger(__name__)

KEY_SIZE = config.cryptography.key_size
SALT_SIZE = config.cryptography.salt_size
IV_SIZE = config.cryptography.iv_size
ITERATIONS = config.cryptography.iterations


def get_encryption_key() -> bytes:
    """
    Get the encryption key from AWS Secrets Manager.

    Returns:
        bytes: The encryption key

    Raises:
        CryptographyError: If key retrieval fails or environment variables are missing
    """
    # Validate only encryption key configuration
    config.validate_database_only()

    try:
        key = get_db_secret(config.encryption_key_secret_name)['encryption_key']

        # Convert string key to bytes if necessary
        if isinstance(key, str):
            key = key.encode('utf-8')

        return key

    except Exception as e:
        raise CryptographyError(f"Failed to get encryption key: {str(e)}")


def derive_key(key: bytes, salt: bytes) -> bytes:
    """
    Derive an encryption key using PBKDF2.

    Args:
        key: The original key
        salt: The salt to use for key derivation

    Returns:
        bytes: The derived key
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(key)


def encrypt(data: Union[str, bytes], key: bytes = None) -> str:
    """
    Encrypt data using AES-256-CBC with PKCS7 padding.

    Args:
        data: The data to encrypt (string or bytes)
        key: Optional encryption key. If not provided, will be retrieved from AWS Secrets Manager.

    Returns:
        str: Base64 encoded string containing salt + IV + encrypted data

    Raises:
        CryptographyError: If encryption fails or data is empty
    """
    try:
        # Validate input data
        if data is None:
            raise CryptographyError("Cannot encrypt None data")
        if isinstance(data, str) and not data.strip():
            raise CryptographyError("Cannot encrypt empty string")
        if isinstance(data, bytes) and not data:
            raise CryptographyError("Cannot encrypt empty bytes")

        # Get key if not provided
        if key is None:
            key = get_encryption_key()

        # Convert string data to bytes if necessary
        if isinstance(data, str):
            data = data.encode('utf-8')

        # Generate a random salt for key derivation
        salt = os.urandom(SALT_SIZE)

        # Generate a random IV
        iv = os.urandom(IV_SIZE)

        # Derive the encryption key
        derived_key = derive_key(key, salt)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(derived_key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Pad the data
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(data) + padder.finalize()

        # Encrypt the data
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

        # Combine salt + IV + encrypted data and encode as base64
        combined = salt + iv + encrypted_data
        return base64.b64encode(combined).decode('utf-8')

    except Exception as e:
        raise CryptographyError(f"Encryption failed: {str(e)}")


def decrypt(data: str, key: bytes = None) -> str:
    r"""
    Decrypt data that was encrypted using AES-256-CBC.

    Args:
        data: The encrypted data, which could be:
            - A base64 encoded string (new format)
            - A hex-encoded string starting with \x (legacy format)
            - A hex-encoded base64 string (legacy format)
        key: Optional encryption key. If not provided, will be retrieved from AWS Secrets Manager.

    Returns:
        str: The decrypted data as a string

    Raises:
        CryptographyError: If decryption fails
    """
    try:
        # Get key if not provided
        if key is None:
            key = get_encryption_key()

        # If the data starts with \x, it's hex encoded
        if data.startswith('\\x'):
            # Remove all \x prefixes
            hex_data = data.replace('\\x', '')

            try:
                # Check if it's a hex-encoded base64 string
                # Base64 strings can end with:
                # - no padding (length % 3 = 0)
                # - = (length % 3 = 2, hex: 3d)
                # - == (length % 3 = 1, hex: 3d3d)
                if hex_data.endswith('3d3d') or hex_data.endswith('3d'):
                    # Convert the hex to a string and then decode base64
                    base64_str = bytes.fromhex(hex_data).decode('utf-8')
                    combined = base64.b64decode(base64_str)
                else:
                    # Convert hex to bytes
                    combined = bytes.fromhex(hex_data)
            except Exception as e:
                raise CryptographyError(f"Failed to decode hex data: {str(e)}")
        else:
            try:
                # Decode as base64 (new format)
                combined = base64.b64decode(data)
            except Exception as e:
                raise CryptographyError(f"Failed to decode base64 data: {str(e)}")

        # Extract salt, IV, and encrypted data
        salt = combined[:SALT_SIZE]
        iv = combined[SALT_SIZE:SALT_SIZE + IV_SIZE]
        encrypted_data = combined[SALT_SIZE + IV_SIZE:]

        # Check if encrypted data length is a multiple of block size
        if len(encrypted_data) % 16 != 0:
            raise CryptographyError(
                f"Encrypted data length ({len(encrypted_data)}) is not a multiple of block size (16). "
                f"This suggests the data may be truncated or corrupted.")

        # Derive the key using the stored salt
        derived_key = derive_key(key, salt)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(derived_key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()

        # Decrypt and unpad the data
        padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()

        return data.decode('utf-8')

    except Exception as e:
        raise CryptographyError(f"Decryption failed: {str(e)}")

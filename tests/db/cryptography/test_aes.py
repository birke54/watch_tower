import os
import pytest
from unittest.mock import patch, MagicMock
from typing import Generator, List
from db.cryptography.aes import encrypt, decrypt, get_encryption_key
from db.exceptions import CryptographyError

# Test data
TEST_KEY = "test_encryption_key_123"
TEST_DATA = "This is a test message"
TEST_BYTES = b"This is test bytes"

@pytest.fixture(autouse=True)
def mock_env_vars() -> Generator[None, None, None]:
    """Mock environment variables"""
    with patch.dict(os.environ, {
        'ENCRYPTION_KEY_SECRET_NAME': 'test-secret',
        'AWS_REGION': 'us-west-2'
    }):
        yield

@pytest.fixture(autouse=True)
def mock_secrets_manager() -> Generator[MagicMock, None, None]:
    """Mock AWS Secrets Manager"""
    with patch('db.cryptography.aes.get_db_secret') as mock_get_secret:
        # Mock get_db_secret to return a dictionary with encryption_key
        mock_get_secret.return_value = {'encryption_key': TEST_KEY}
        yield mock_get_secret

def test_get_encryption_key_success(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test successful retrieval of encryption key"""
    key = get_encryption_key()
    assert isinstance(key, bytes)
    assert key == TEST_KEY.encode('utf-8')

def test_get_encryption_key_failure(mock_env_vars: None) -> None:
    """Test key retrieval failure"""
    with patch('db.cryptography.aes.get_db_secret', side_effect=Exception("Secret error")):
        with pytest.raises(CryptographyError) as exc_info:
            get_encryption_key()
        assert "Failed to get encryption key" in str(exc_info.value)

def test_encrypt_string(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test encryption of string data"""
    encrypted = encrypt(TEST_DATA)
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0
    # Verify the encrypted data is base64 encoded
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in encrypted)

def test_encrypt_bytes(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test encryption of bytes data"""
    encrypted = encrypt(TEST_BYTES)
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0
    # Verify the encrypted data is base64 encoded
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in encrypted)

def test_encrypt_with_custom_key(mock_env_vars: None) -> None:
    """Test encryption with a custom key"""
    custom_key = b"custom_test_key"
    encrypted = encrypt(TEST_DATA, key=custom_key)
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0

def test_encrypt_failure(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test encryption failure with invalid data"""
    with pytest.raises(CryptographyError):
        encrypt("")  # Use empty string instead of None to match expected type

def test_decrypt_success(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test successful decryption of encrypted data"""
    # Encrypt test data
    encrypted = encrypt(TEST_DATA)
    # Decrypt the data
    decrypted = decrypt(encrypted)
    # Verify the decrypted data matches the original
    assert decrypted == TEST_DATA

def test_decrypt_bytes(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test successful decryption of encrypted bytes data"""
    # Encrypt test data
    encrypted = encrypt(TEST_BYTES)
    # Decrypt the data
    decrypted = decrypt(encrypted)
    # Verify the decrypted data matches the original
    assert decrypted == TEST_BYTES.decode('utf-8')

def test_decrypt_with_custom_key(mock_env_vars: None) -> None:
    """Test decryption with a custom key"""
    custom_key = b"custom_test_key"
    # Encrypt with custom key
    encrypted = encrypt(TEST_DATA, key=custom_key)
    # Decrypt with same custom key
    decrypted = decrypt(encrypted, key=custom_key)
    assert decrypted == TEST_DATA

def test_decrypt_invalid_data(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test decryption failure with invalid data"""
    with pytest.raises(CryptographyError):
        decrypt("invalid_base64_data")

def test_decrypt_empty_data(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test decryption failure with empty data"""
    with pytest.raises(CryptographyError):
        decrypt("")

def test_encrypt_decrypt_roundtrip(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test multiple encrypt-decrypt roundtrips with different data"""
    test_cases: List[str] = [
        "Simple string",
        "String with special chars: !@#$%^&*()",
        "String with numbers: 1234567890",
        "String with spaces and tabs\t\t",
        "String with newlines\n\n",
        "String with unicode: 你好世界",
        "Very long string " * 100
    ]

    for test_data in test_cases:
        encrypted = encrypt(test_data)
        decrypted = decrypt(encrypted)
        assert decrypted == test_data

def test_encryption_deterministic(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test that encrypting the same data multiple times produces different results
    (due to random IV and salt)"""
    encrypted1 = encrypt(TEST_DATA)
    encrypted2 = encrypt(TEST_DATA)
    assert encrypted1 != encrypted2  # Should be different due to random IV/salt

def test_decryption_deterministic(mock_env_vars: None, mock_secrets_manager: MagicMock) -> None:
    """Test that decrypting the same encrypted data multiple times produces the same result"""
    encrypted = encrypt(TEST_DATA)
    decrypted1 = decrypt(encrypted)
    decrypted2 = decrypt(encrypted)
    assert decrypted1 == decrypted2  # Should be the same
"""Unit tests for AES cryptography module."""
import os
from typing import Generator, List
from unittest.mock import MagicMock, patch

import pytest

from aws.exceptions import AWSCredentialsError, SecretsManagerError
from db.cryptography.aes import decrypt, encrypt, get_encryption_key
from db.exceptions import CryptographyError, CryptographyInputError

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


def test_get_encryption_key_success() -> None:
    """Test successful retrieval of encryption key"""
    key = get_encryption_key()
    assert isinstance(key, bytes)
    assert key == TEST_KEY.encode('utf-8')


def test_get_encryption_key_failure_aws_credentials_error() -> None:
    """Test key retrieval failure with SecretsManagerError"""
    with patch('db.cryptography.aes.get_db_secret', side_effect=AWSCredentialsError("Secret error")):
        with pytest.raises(CryptographyError) as exc_info:
            get_encryption_key()
        assert "Failed to get encryption key" in str(exc_info.value)
        assert "Secret error" in str(exc_info.value)


def test_get_encryption_key_failure_aws_credentials_error() -> None:
    """Test key retrieval failure with AWSCredentialsError"""
    with patch('db.cryptography.aes.get_db_secret', side_effect=AWSCredentialsError("No credentials")):
        with pytest.raises(CryptographyError) as exc_info:
            get_encryption_key()
        assert "Failed to get encryption key" in str(exc_info.value)
        assert "No credentials" in str(exc_info.value)


def test_get_encryption_key_failure_key_error() -> None:
    """Test key retrieval failure when encryption_key is missing from secret"""
    with patch('db.cryptography.aes.get_db_secret', return_value={'wrong_key': 'value'}):
        with pytest.raises(CryptographyError) as exc_info:
            get_encryption_key()
        assert "Failed to get encryption key" in str(exc_info.value)


def test_get_encryption_key_failure_type_error() -> None:
    """Test key retrieval failure when encryption_key is not a string"""
    with patch('db.cryptography.aes.get_db_secret', return_value={'encryption_key': 12345}):
        with pytest.raises(CryptographyError) as exc_info:
            get_encryption_key()
        assert "Failed to get encryption key" in str(exc_info.value)


def test_encrypt_string() -> None:
    """Test encryption of string data"""
    encrypted = encrypt(TEST_DATA)
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0
    # Verify the encrypted data is base64 encoded
    assert all(
        c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in encrypted)


def test_encrypt_bytes() -> None:
    """Test encryption of bytes data"""
    encrypted = encrypt(TEST_BYTES)
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0
    # Verify the encrypted data is base64 encoded
    assert all(
        c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in encrypted)


def test_encrypt_with_custom_key() -> None:
    """Test encryption with a custom key"""
    custom_key = b"custom_test_key"
    encrypted = encrypt(TEST_DATA, key=custom_key)
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0


def test_encrypt_failure_empty_string() -> None:
    """Test encryption failure with empty string"""
    with pytest.raises(CryptographyInputError) as exc_info:
        encrypt("")
    assert "Cannot encrypt empty string data" in str(exc_info.value)


def test_encrypt_failure_none() -> None:
    """Test encryption failure with None input"""
    with pytest.raises(CryptographyInputError) as exc_info:
        encrypt(None)  # type: ignore
    assert "Cannot encrypt None data" in str(exc_info.value)


def test_encrypt_failure_empty_bytes() -> None:
    """Test encryption failure with empty bytes"""
    with pytest.raises(CryptographyInputError) as exc_info:
        encrypt(b"")
    assert "Cannot encrypt empty bytes data" in str(exc_info.value)


def test_encrypt_failure_whitespace_only() -> None:
    """Test encryption failure with whitespace-only string"""
    with pytest.raises(CryptographyInputError) as exc_info:
        encrypt("   \t\n  ")
    assert "Cannot encrypt empty string data" in str(exc_info.value)


def test_encrypt_failure_key_retrieval_error() -> None:
    """Test encryption failure when key retrieval fails"""
    with patch('db.cryptography.aes.get_encryption_key', side_effect=CryptographyError("Key error")):
        with pytest.raises(CryptographyError) as exc_info:
            encrypt(TEST_DATA)
        assert "Key error" in str(exc_info.value)


def test_encrypt_metrics_success(monkeypatch) -> None:
    """Test that success metrics are incremented on successful encryption"""
    from utils.metrics import MetricDataPointName
    
    inc_mock = MagicMock()
    monkeypatch.setattr('db.cryptography.aes.inc_counter_metric', inc_mock)
    
    encrypt(TEST_DATA)
    
    # Check that success metric was called with the correct enum value
    inc_mock.assert_any_call(MetricDataPointName.AES_ENCRYPT_SUCCESS_COUNT)


def test_encrypt_metrics_error(monkeypatch) -> None:
    """Test that error metrics are incremented on encryption failure"""
    from utils.metrics import MetricDataPointName
    
    inc_mock = MagicMock()
    monkeypatch.setattr('db.cryptography.aes.inc_counter_metric', inc_mock)
    
    with pytest.raises(CryptographyInputError):
        encrypt("")
    
    # Check that error metric was called with the correct enum value
    inc_mock.assert_any_call(MetricDataPointName.AES_ENCRYPT_ERROR_COUNT)


def test_decrypt_success() -> None:
    """Test successful decryption of encrypted data"""
    # Encrypt test data
    encrypted = encrypt(TEST_DATA)
    # Decrypt the data
    decrypted = decrypt(encrypted)
    # Verify the decrypted data matches the original
    assert decrypted == TEST_DATA


def test_decrypt_bytes() -> None:
    """Test successful decryption of encrypted bytes data"""
    # Encrypt test data
    encrypted = encrypt(TEST_BYTES)
    # Decrypt the data
    decrypted = decrypt(encrypted)
    # Verify the decrypted data matches the original
    assert decrypted == TEST_BYTES.decode('utf-8')


def test_decrypt_with_custom_key() -> None:
    """Test decryption with a custom key"""
    custom_key = b"custom_test_key"
    # Encrypt with custom key
    encrypted = encrypt(TEST_DATA, key=custom_key)
    # Decrypt with same custom key
    decrypted = decrypt(encrypted, key=custom_key)
    assert decrypted == TEST_DATA


def test_decrypt_invalid_base64_data() -> None:
    """Test decryption failure with invalid base64 data"""
    with pytest.raises(CryptographyError) as exc_info:
        decrypt("invalid_base64_data")
    assert "Decryption failed" in str(exc_info.value)


def test_decrypt_empty_data() -> None:
    """Test decryption failure with empty string"""
    with pytest.raises(CryptographyInputError) as exc_info:
        decrypt("")
    assert "Cannot decrypt empty string data" in str(exc_info.value)


def test_decrypt_none_input() -> None:
    """Test decryption failure with None input"""
    with pytest.raises(CryptographyInputError) as exc_info:
        decrypt(None)  # type: ignore
    assert "Cannot decrypt None data" in str(exc_info.value)


def test_decrypt_non_string_input() -> None:
    """Test decryption failure with non-string input"""
    with pytest.raises(CryptographyInputError) as exc_info:
        decrypt(12345)  # type: ignore
    assert "Cannot decrypt non-string data" in str(exc_info.value)
    assert "int" in str(exc_info.value)


def test_decrypt_whitespace_only() -> None:
    """Test decryption failure with whitespace-only string"""
    with pytest.raises(CryptographyInputError) as exc_info:
        decrypt("   \t\n  ")
    assert "Cannot decrypt empty string data" in str(exc_info.value)


def test_decrypt_corrupted_data_wrong_block_size() -> None:
    """Test decryption failure with corrupted data (wrong block size)"""
    # Create invalid encrypted data that's not a multiple of 16 bytes
    # We'll create a valid base64 string but with wrong length after decoding
    import base64
    # Create data that when decoded is not a multiple of 16
    invalid_data = base64.b64encode(b"short").decode('utf-8')
    
    with pytest.raises(CryptographyError) as exc_info:
        decrypt(invalid_data)
    assert "not a multiple of block size" in str(exc_info.value)


def test_decrypt_wrong_key() -> None:
    """Test decryption failure when wrong key is used"""
    # Encrypt with one key
    key1 = b"correct_key_12345678901234567890"
    encrypted = encrypt(TEST_DATA, key=key1)
    
    # Try to decrypt with different key
    key2 = b"wrong_key_123456789012345678901"
    with pytest.raises(CryptographyError) as exc_info:
        decrypt(encrypted, key=key2)
    assert "Decryption failed" in str(exc_info.value)


def test_decrypt_legacy_hex_format() -> None:
    """Test decryption with legacy hex-encoded format"""
    # Encrypt data normally
    encrypted = encrypt(TEST_DATA)
    
    # Convert to hex format (legacy) - decode base64 first, then hex encode
    import base64
    decoded = base64.b64decode(encrypted)
    # Create hex string with \x prefix format
    hex_encoded = '\\x' + '\\x'.join(f'{b:02x}' for b in decoded)
    
    # Should be able to decrypt the hex-encoded format
    decrypted = decrypt(hex_encoded)
    assert decrypted == TEST_DATA


def test_decrypt_legacy_hex_base64_format() -> None:
    """Test decryption with legacy hex-encoded base64 format (ending with padding)"""
    # Encrypt data normally
    encrypted = encrypt(TEST_DATA)
    
    # Convert to hex-encoded base64 format (legacy) - encode each char as hex
    # This format ends with '3d' or '3d3d' (base64 padding = or ==)
    hex_base64 = '\\x' + '\\x'.join(f'{ord(c):02x}' for c in encrypted)
    
    # Should be able to decrypt the hex-encoded base64 format
    decrypted = decrypt(hex_base64)
    assert decrypted == TEST_DATA


def test_decrypt_key_retrieval_error() -> None:
    """Test decryption failure when key retrieval fails"""
    encrypted = encrypt(TEST_DATA)
    with patch('db.cryptography.aes.get_encryption_key', side_effect=CryptographyError("Key error")):
        with pytest.raises(CryptographyError) as exc_info:
            decrypt(encrypted)
        assert "Key error" in str(exc_info.value)


def test_decrypt_metrics_success(monkeypatch) -> None:
    """Test that success metrics are incremented on successful decryption"""
    from utils.metrics import MetricDataPointName
    
    inc_mock = MagicMock()
    monkeypatch.setattr('db.cryptography.aes.inc_counter_metric', inc_mock)
    
    encrypted = encrypt(TEST_DATA)
    decrypt(encrypted)
    
    # Check that success metric was called with the correct enum value
    inc_mock.assert_any_call(MetricDataPointName.AES_DECRYPT_SUCCESS_COUNT)


def test_decrypt_metrics_error(monkeypatch) -> None:
    """Test that error metrics are incremented on decryption failure"""
    from utils.metrics import MetricDataPointName
    
    inc_mock = MagicMock()
    monkeypatch.setattr('db.cryptography.aes.inc_counter_metric', inc_mock)
    
    with pytest.raises(CryptographyInputError):
        decrypt("")
    
    # Check that error metric was called with the correct enum value
    inc_mock.assert_any_call(MetricDataPointName.AES_DECRYPT_ERROR_COUNT)


def test_encrypt_decrypt_roundtrip() -> None:
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


def test_encryption_deterministic() -> None:
    """Test that encrypting the same data multiple times produces different results
    (due to random IV and salt)"""
    encrypted1 = encrypt(TEST_DATA)
    encrypted2 = encrypt(TEST_DATA)
    assert encrypted1 != encrypted2  # Should be different due to random IV/salt


def test_decryption_deterministic() -> None:
    """Test that decrypting the same encrypted data multiple times produces the same result"""
    encrypted = encrypt(TEST_DATA)
    decrypted1 = decrypt(encrypted)
    decrypted2 = decrypt(encrypted)
    assert decrypted1 == decrypted2  # Should be the same

## Encrypt Password

WITH ivs AS (
  SELECT
    vendor_id,
    gen_random_bytes(16) AS iv
  FROM vendors
  WHERE plain_password IS NOT NULL
)
UPDATE vendors v
SET
  password_iv  = ivs.iv,
  password_enc = encrypt_iv(
    convert_to(v.plain_password, 'utf8'),                       -- data bytea
    convert_to('<master key>','utf8'),  -- key bytea
    ivs.iv,                                                     -- iv bytea
    'aes-cbc'                                                   -- type text
  )
FROM ivs
WHERE v.vendor_id = ivs.vendor_id;


import json
import uuid
from jwkest import jws
from jwkest import jwe
from jwkest.jwe import JWE
from jwkest.jws import NoSuitableSigningKeys
from oic.oic.message import JasonWebToken
from oic.utils.time_util import utc_time_sans_frac

__author__ = 'roland'


class JWT(object):
    def __init__(self, keyjar, iss='', lifetime=0, sign_alg='RS256',
                 msgtype=JasonWebToken, encrypt=False, enc_enc="A128CBC-HS256",
                 enc_alg="RSA1_5"):
        self.iss = iss
        self.lifetime = lifetime
        self.sign_alg = sign_alg
        self.keyjar = keyjar  # my signing key
        self.message_type = msgtype
        self.encrypt = encrypt
        self.enc_alg = enc_alg
        self.enc_enc = enc_enc

    def _encrypt(self, payload, cty='JWT'):
        keys = self.keyjar.get_encrypt_key(owner='')
        kwargs = {"alg": self.enc_alg, "enc": self.enc_enc}

        if cty:
            kwargs["cty"] = cty

        # use the clients public key for encryption
        _jwe = JWE(payload, **kwargs)
        return _jwe.encrypt(keys, context="public")

    def pack(self, kid='', owner='', **kwargs):
        keys = self.keyjar.get_signing_key(jws.alg2keytype(self.sign_alg),
                                           owner=owner, kid=kid)

        if not keys:
            raise NoSuitableSigningKeys('kid={}'.format(kid))

        key = keys[0]  # Might be more then one if kid == ''

        if key.kid:
            kwargs['kid'] = key.kid

        iat = utc_time_sans_frac()
        if not 'exp' in kwargs:
            kwargs['exp'] = iat + self.lifetime

        try:
            _encrypt = kwargs['encrypt']
        except KeyError:
            _encrypt = self.encrypt
        else:
            del kwargs['encrypt']

        _jwt = self.message_type(iss=self.iss, iat=iat, **kwargs)

        if 'jti' in self.message_type.c_param:
            try:
                _jti = kwargs['jti']
            except:
                _jti = uuid.uuid4().hex

            _jwt['jti'] = _jti

        _jws = _jwt.to_jwt([key], self.sign_alg)
        if _encrypt:
            return self._encrypt(_jws)
        else:
            return _jws

    def _verify(self, rj, token):
        _msg = json.loads(rj.jwt.part[1].decode('utf8'))
        if _msg['iss'] == self.iss:
            owner = ''
        else:
            owner = _msg['iss']

        keys = self.keyjar.get_signing_key(jws.alg2keytype(rj.jwt.headers['alg']),
                                           owner=owner)
        return rj.verify_compact(token, keys)

    def _decrypt(self, rj, token):
        keys = self.keyjar.get_verify_key(owner='')
        msg = rj.decrypt(token, keys)
        _rj = jws.factory(msg)
        if not _rj:
            raise KeyError()
        else:
            return self._verify(_rj, msg)

    def unpack(self, token):
        if not token:
            raise KeyError

        _rj = jws.factory(token)
        if _rj:
            info = self._verify(_rj, token)
        else:
            _rj = jwe.factory(token)
            if not _rj:
                raise KeyError()
            info = self._decrypt(_rj, token)

        if self.message_type:
            return self.message_type(**info)
        else:
            return info

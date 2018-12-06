'use strict';
var jwt = require('jsonwebtoken');  
var jwkToPem = require('jwk-to-pem');
var AWS = require('aws-sdk')
const request = require('request');


var ssm = new AWS.SSM();

var params_done = false;
var params_errored = false;
var err_message;

var store_params = {};

var params = {
  Names: [ 
    'CognitoUserPoolId',
    'CognitoRegion',
    'CognitoCallbackUrl',
    'CognitoUserPoolClientId',
    'CognitoPoolDomainName'
  ],
};

var iss;
var domain;
var base_url;
var req_args;
var pems;


try {
  ssm.getParameters(params, function(err, data) {
    if (err) {
      params_errored = true; // an error occurred
      err_message = err;
    } else {
      data.Parameters.forEach((element) => {
         store_params[element.Name] = element.Value
      });

      iss = 'https://cognito-idp.' + store_params['CognitoRegion'] + '.amazonaws.com/' + store_params['CognitoUserPoolId'];
      base_url = "https://" + store_params['CognitoCallbackUrl'] + '/public/index.html';
      req_args = "?response_type=token&client_id=" + store_params['CognitoUserPoolClientId'];
      domain = "https://" + store_params['CognitoPoolDomainName'] + ".auth." + store_params['CognitoRegion'] + ".amazoncognito.com/login";

      var jwks_url = iss + "/.well-known/jwks.json";
      request(jwks_url, { json: true }, (err, res, body) => {
        if (err) { 
          params_errored = true
          err_message = err;
          return      
        }
        pems = {};
        var keys = body.keys;
        for(var i = 0; i < keys.length; i++) {
            //Convert each key to PEM
            var key_id = keys[i].kid;
            var modulus = keys[i].n;
            var exponent = keys[i].e;
            var key_type = keys[i].kty;
            var jwk = { kty: key_type, n: modulus, e: exponent};
            var pem = jwkToPem(jwk);
            pems[key_id] = pem;
        }
        params_done = true;
      });
    }
  });
} catch(err) {
  params_errored = true;
  err_message = err.message;
}

const response503 = {
    status: '503',
    statusDescription: 'Not Accepted'
};


const responseCustom = (message) => {
    return {
      status: '503',
      statusDescription: message,
      headers: {
        'cache-control': [{
            key: 'Cache-Control',
            value: 'must-revalidate'
        }],
      }
    };
}

const format_redir = (requested_resource) => {
    return {
        status: '302',
        statusDescription: 'Found',
        headers: {
            location: [{
                key: 'Location',
                value: domain + req_args + "&redirect_uri=" + base_url + "&debug=" + requested_resource,
            }],
        },
    };
}

exports.handler = (event, context, callback) => {
    const cfrequest = event.Records[0].cf.request;
    const resource = cfrequest.uri
    const headers = cfrequest.headers;

    if (params_errored) {
      callback(null, responseCustom(err_message));
    }

    if (!params_done) {
      callback(null, response503);
      return false;    
    }

    try {
        //Fail if no authorization header found
        if(!headers.cookie) {
            console.log("no auth header");
            callback(null, format_redir("no_cookie"));
            return false;
        }
    
    
        var cookie = null;
        for (let i = 0; i < headers.cookie.length; i++) {
            if (headers.cookie[i].value.indexOf("antiope-auth-at-edge") >= 0) {
                cookie = headers.cookie[i].value.split("=")[1];
            }
        }
        
        if(!cookie) {
            console.log("no auth header");
            callback(null, format_redir("no_cookie_2"));
            return false;
        }
    
    
        //Fail if the token is not jwt
        var decodedJwt = jwt.decode(cookie, {complete: true});
        if (!decodedJwt) {
            console.log("Not a valid JWT token");
            callback(null, format_redir("no_cookie_3"));
            return false;
        }
    
        //Fail if token is not from your UserPool
        if (decodedJwt.payload.iss != iss) {
            console.log("invalid issuer");
            callback(null, format_redir("no_cookie_4"));
            return false;
        }
    
        //Reject the jwt if it's not an 'Access Token'
        if (decodedJwt.payload.token_use != 'access') {
            console.log("Not an access token");
            callback(null, format_redir("no_cookie_5"));
            return false;
        }
    
        //Get the kid from the token and retrieve corresponding PEM
        var kid = decodedJwt.header.kid;
        var pem = pems[kid];
        if (!pem) {
            console.log('Invalid access token');
            callback(null, format_redir("no_cookie_6"));
            return false;
        }
    
        //Verify the signature of the JWT token to ensure it's really coming from your User Pool
        jwt.verify(cookie, pem, { issuer: iss }, function(err, payload) {
          if(err) {
            console.log('Token failed verification');
            callback(null, format_redir("no_cookie_7"));
            return false;
          } else {
            //Valid token. 
            console.log('Successful verification');
            //remove authorization header
            delete cfrequest.headers.authorization;
            //CloudFront can proceed to fetch the content from origin
            callback(null, cfrequest);
            return true;
          }
        });
   } catch (err) {
        callback(null, format_redir(err.message))
        return false;
    } 
};






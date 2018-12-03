'use strict';
var jwt = require('jsonwebtoken');  
var jwkToPem = require('jwk-to-pem');

/*
verify values above
*/
var JWKS = '#s'
var USERPOOLID = "#"

var region = 'us-east-1';
var iss = 'https://cognito-idp.' + region + '.amazonaws.com/' + USERPOOLID;
const domain = "#
const base_url = "#"
const client_id = "#"
const req_args = "?response_type=token&client_id=" + client_id


var pems;

pems = {};
var keys = JSON.parse(JWKS).keys;
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

const response401 = {
    status: '401',
    statusDescription: 'Unauthorized'
};


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
    console.log('getting started');
    console.log('USERPOOLID=' + USERPOOLID);
    console.log('region=' + region);
    console.log('pems=' + pems);
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






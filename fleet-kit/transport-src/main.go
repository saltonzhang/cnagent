// WireGuard carries IP; mTLS admits the dedicated CN identity. No SSH transport.
package main

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"errors"
	"flag"
	"io"
	"log"
	"math/big"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

func writePEM(dir, name, kind string, b []byte) error {
	return os.WriteFile(filepath.Join(dir, name), pem.EncodeToMemory(&pem.Block{Type: kind, Bytes: b}), 0600)
}
func generate(dir string) error {
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	if _, e := os.Stat(filepath.Join(dir, "ca-key.pem")); e == nil {
		return errors.New("refusing_existing_CA")
	}
	key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	now := time.Now()
	serial := func() *big.Int { n, _ := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 120)); return n }
	ca := &x509.Certificate{SerialNumber: serial(), Subject: pkix.Name{CommonName: "CN Agent WG pilot CA"}, NotBefore: now.Add(-time.Hour), NotAfter: now.AddDate(1, 0, 0), IsCA: true, BasicConstraintsValid: true, KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageCRLSign}
	der, e := x509.CreateCertificate(rand.Reader, ca, ca, &key.PublicKey, key)
	if e != nil {
		return e
	}
	if e = writePEM(dir, "ca.pem", "CERTIFICATE", der); e != nil {
		return e
	}
	kb, _ := x509.MarshalPKCS8PrivateKey(key)
	if e = writePEM(dir, "ca-key.pem", "PRIVATE KEY", kb); e != nil {
		return e
	}
	for _, name := range []string{"server", "cn-pilot"} {
		k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
		c := &x509.Certificate{SerialNumber: serial(), Subject: pkix.Name{CommonName: name}, NotBefore: now.Add(-time.Hour), NotAfter: now.AddDate(0, 3, 0), BasicConstraintsValid: true, KeyUsage: x509.KeyUsageDigitalSignature}
		if name == "server" {
			c.ExtKeyUsage = []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}
			c.IPAddresses = []net.IP{net.ParseIP("10.9.8.30")}
		} else {
			c.ExtKeyUsage = []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth}
		}
		b, err := x509.CreateCertificate(rand.Reader, c, ca, &k.PublicKey, key)
		if err != nil {
			return err
		}
		if err = writePEM(dir, name+".pem", "CERTIFICATE", b); err != nil {
			return err
		}
		b, _ = x509.MarshalPKCS8PrivateKey(k)
		if err = writePEM(dir, name+"-key.pem", "PRIVATE KEY", b); err != nil {
			return err
		}
		if name == "cn-pilot" {
			if err = os.WriteFile(filepath.Join(dir, "allowed-serial"), []byte(c.SerialNumber.Text(16)+"\n"), 0600); err != nil {
				return err
			}
		}
	}
	return nil
}
func config(cert, key, ca string, server bool, allow string) (*tls.Config, error) {
	c, e := tls.LoadX509KeyPair(cert, key)
	if e != nil {
		return nil, e
	}
	b, e := os.ReadFile(ca)
	if e != nil {
		return nil, e
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(b) {
		return nil, errors.New("invalid_CA")
	}
	t := &tls.Config{MinVersion: tls.VersionTLS12, Certificates: []tls.Certificate{c}, NextProtos: []string{"http/1.1"}}
	if server {
		t.ClientCAs = pool
		t.ClientAuth = tls.RequireAndVerifyClientCert
		t.VerifyConnection = func(s tls.ConnectionState) error { return admitted(s.PeerCertificates, allow) }
	} else {
		t.RootCAs = pool
	}
	return t, nil
}
func admitted(certs []*x509.Certificate, allow string) error {
	b, e := os.ReadFile(allow)
	if e != nil || len(certs) == 0 {
		return errors.New("identity_unavailable")
	}
	for _, line := range strings.Fields(string(b)) {
		if serial, ok := new(big.Int).SetString(line, 16); ok && serial.Cmp(certs[0].SerialNumber) == 0 {
			return nil
		}
	}
	return errors.New("identity_revoked")
}
func pipes(a, b net.Conn) {
	defer a.Close()
	defer b.Close()
	done := make(chan struct{}, 1)
	go func() { io.Copy(a, b); done <- struct{}{} }()
	go func() { io.Copy(b, a); done <- struct{}{} }()
	<-done
}
func privateIP(ip net.IP) bool {
	// RFC 6052 well-known DNS64 prefix: validate the embedded IPv4 before
	// allowing JP's own NAT64 path. Private/loopback IPv4 remain forbidden.
	_, nat64, _ := net.ParseCIDR("64:ff9b::/96")
	if ip.To4() == nil && nat64.Contains(ip) {
		return privateIP(net.IP(ip.To16()[12:16]))
	}
	if !ip.IsGlobalUnicast() || ip.IsPrivate() || ip.IsLoopback() || ip.IsLinkLocalUnicast() {
		return true
	}
	for _, cidr := range []string{"0.0.0.0/8", "64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "2001::/32", "100.64.0.0/10", "192.0.0.0/24", "192.0.2.0/24", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "240.0.0.0/4", "2001:db8::/32"} {
		_, n, _ := net.ParseCIDR(cidr)
		if n.Contains(ip) {
			return true
		}
	}
	return false
}

type lookupIPs func(context.Context, string) ([]net.IPAddr, error)
type dialIP func(context.Context, string, string) (net.Conn, error)

func publicDial(ctx context.Context, network, address string) (net.Conn, error) {
	d := &net.Dialer{Timeout: 6 * time.Second}
	return publicDialWith(ctx, address, net.DefaultResolver.LookupIPAddr, d.DialContext)
}
func publicDialWith(parent context.Context, address string, lookup lookupIPs, dial dialIP) (net.Conn, error) {
	host, port, e := net.SplitHostPort(address)
	if e != nil || (port != "80" && port != "443") {
		return nil, errors.New("target_port_refused")
	}
	ctx, cancel := context.WithTimeout(parent, 12*time.Second)
	defer cancel()
	ips, e := lookup(ctx, host)
	if e != nil || len(ips) == 0 {
		return nil, errors.New("target_dns_failed")
	}
	// Pin every connection to a checked IP. An unsafe answer never gets
	// dialled and cannot poison the other, valid answers for this host.
	targets := make([]net.IPAddr, 0, len(ips))
	seen := map[string]bool{}
	for _, ip := range ips {
		if privateIP(ip.IP) || ip.Zone != "" || seen[ip.IP.String()] {
			continue
		}
		targets = append(targets, ip)
		seen[ip.IP.String()] = true
	}
	if len(targets) == 0 {
		return nil, errors.New("private_target_refused")
	}
	sort.SliceStable(targets, func(i, j int) bool { return targets[i].IP.To4() != nil && targets[j].IP.To4() == nil })
	// Bounded Happy Eyeballs style racing; a dead family must not consume
	// the caller's entire budget before another checked address is tried.
	v4, v6 := 0, 0
	bounded := make([]net.IPAddr, 0, 8)
	for _, ip := range targets {
		if ip.IP.To4() != nil {
			if v4 == 4 {
				continue
			}
			v4++
		} else {
			if v6 == 4 {
				continue
			}
			v6++
		}
		bounded = append(bounded, ip)
	}
	type attempt struct {
		conn net.Conn
		err  error
	}
	results := make(chan attempt)
	for i, ip := range bounded {
		go func(i int, ip net.IPAddr) {
			timer := time.NewTimer(time.Duration(i) * 200 * time.Millisecond)
			defer timer.Stop()
			select {
			case <-timer.C:
			case <-ctx.Done():
				return
			}
			c, err := dial(ctx, "tcp", net.JoinHostPort(ip.IP.String(), port))
			select {
			case results <- attempt{c, err}:
			case <-ctx.Done():
				if c != nil {
					c.Close()
				}
			}
		}(i, ip)
	}
	for range bounded {
		select {
		case r := <-results:
			if r.err == nil && r.conn != nil {
				return r.conn, nil
			}
		case <-ctx.Done():
			return nil, errors.New("target_connect_timeout")
		}
	}
	return nil, errors.New("target_unavailable")
}
func egress() http.Handler {
	transport := &http.Transport{Proxy: nil, DialContext: publicDial, ForceAttemptHTTP2: false, ResponseHeaderTimeout: 30 * time.Second}
	proxy := &httputil.ReverseProxy{Director: func(r *http.Request) {
		r.RequestURI = ""
		r.Header.Del("Proxy-Authorization")
		r.Header.Del("Proxy-Connection")
	}, Transport: transport, FlushInterval: -1, ErrorLog: log.New(io.Discard, "", 0), ErrorHandler: func(w http.ResponseWriter, r *http.Request, e error) { http.Error(w, "egress_unavailable", 502) }}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "CONNECT" {
			c, e := publicDial(r.Context(), "tcp", r.Host)
			if e != nil {
				code, reason := http.StatusBadGateway, "egress_connection_failed"
				switch e.Error() {
				case "target_port_refused", "private_target_refused":
					code, reason = http.StatusForbidden, "egress_target_refused"
				case "target_dns_failed":
					reason = "egress_dns_failed"
				case "target_connect_timeout":
					code, reason = http.StatusGatewayTimeout, "egress_connect_timeout"
				}
				w.Header().Set("X-CN-Agent-Egress-Error", reason)
				http.Error(w, reason, code)
				return
			}
			h, ok := w.(http.Hijacker)
			if !ok {
				c.Close()
				http.Error(w, "transport_unavailable", 500)
				return
			}
			a, rw, e := h.Hijack()
			if e != nil {
				c.Close()
				return
			}
			rw.WriteString("HTTP/1.1 200 Connection Established\r\n\r\n")
			rw.Flush()
			if n := rw.Reader.Buffered(); n > 0 {
				b, _ := rw.Reader.Peek(n)
				c.Write(b)
				rw.Reader.Discard(n)
			}
			pipes(a, c)
			return
		}
		if r.URL.Scheme != "http" || r.URL.Host == "" || r.URL.User != nil {
			http.Error(w, "invalid_proxy_target", 400)
			return
		}
		proxy.ServeHTTP(w, r)
	})
}
func main() {
	role := flag.String("role", "", "generate|client|api|egress")
	dir := flag.String("dir", "", "certificate output")
	listen := flag.String("listen", "127.0.0.1:0", "")
	remote := flag.String("remote", "", "")
	cert := flag.String("cert", "", "")
	key := flag.String("key", "", "")
	ca := flag.String("ca", "", "")
	allow := flag.String("allow-serial", "", "")
	flag.Parse()
	log.SetFlags(0)
	if *role == "generate" {
		if e := generate(*dir); e != nil {
			log.Fatal("certificate_generation_failed")
		}
		return
	}
	t, e := config(*cert, *key, *ca, *role != "client", *allow)
	if e != nil {
		log.Fatal("certificate_config_failed")
	}
	if *role == "client" {
		h, _, e := net.SplitHostPort(*remote)
		if e != nil {
			log.Fatal("invalid_remote")
		}
		t.ServerName = h
		h, _, e = net.SplitHostPort(*listen)
		if e != nil || !net.ParseIP(h).IsLoopback() {
			log.Fatal("client_must_bind_loopback")
		}
		l, e := net.Listen("tcp", *listen)
		if e != nil {
			log.Fatal("listen_failed")
		}
		for {
			c, e := l.Accept()
			if e != nil {
				log.Fatal("accept_failed")
			}
			go func() {
				d := &net.Dialer{Timeout: 10 * time.Second}
				u, e := tls.DialWithDialer(d, "tcp", *remote, t)
				if e != nil {
					c.Close()
					return
				}
				pipes(c, u)
			}()
		}
	}
	var handler http.Handler
	if *role == "api" {
		u, e := url.Parse(*remote)
		if e != nil || u.Scheme != "http" || u.Host != "127.0.0.1:3425" {
			log.Fatal("invalid_api_backend")
		}
		p := httputil.NewSingleHostReverseProxy(u)
		p.FlushInterval = -1
		p.ErrorLog = log.New(io.Discard, "", 0)
		p.ErrorHandler = func(w http.ResponseWriter, r *http.Request, e error) { http.Error(w, "magpie_unavailable", 502) }
		handler = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if !strings.HasPrefix(r.URL.Path, "/v1/") {
				http.Error(w, "api_path_refused", 403)
				return
			}
			r.Header.Del("Forwarded")
			r.Header.Del("X-Forwarded-For")
			r.Header.Del("X-Real-IP")
			p.ServeHTTP(w, r)
		})
	} else if *role == "egress" {
		handler = egress()
	} else {
		log.Fatal("invalid_role")
	}
	wrapped := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.TLS == nil || admitted(r.TLS.PeerCertificates, *allow) != nil {
			http.Error(w, "identity_refused", 403)
			return
		}
		handler.ServeHTTP(w, r)
	})
	s := &http.Server{Addr: *listen, Handler: wrapped, TLSConfig: t, ReadHeaderTimeout: 10 * time.Second, IdleTimeout: 90 * time.Second, MaxHeaderBytes: 1 << 20, ErrorLog: log.New(io.Discard, "", 0)}
	if e = s.ListenAndServeTLS("", ""); e != nil {
		log.Fatal("server_stopped")
	}
}

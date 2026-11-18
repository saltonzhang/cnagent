package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestClientIdentityAndRevocation(t *testing.T) {
	d := t.TempDir()
	if e := generate(d); e != nil {
		t.Fatal(e)
	}
	f := func(n string) string { return filepath.Join(d, n) }
	server, e := config(f("server.pem"), f("server-key.pem"), f("ca.pem"), true, f("allowed-serial"))
	if e != nil {
		t.Fatal(e)
	}
	s := httptest.NewUnstartedServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if admitted(r.TLS.PeerCertificates, f("allowed-serial")) != nil {
			w.WriteHeader(403)
			return
		}
		w.WriteHeader(204)
	}))
	s.TLS = server
	s.StartTLS()
	defer s.Close()
	// Use ServerName to verify the issued IP SAN against the local test server.
	client, e := config(f("cn-pilot.pem"), f("cn-pilot-key.pem"), f("ca.pem"), false, "")
	if e != nil {
		t.Fatal(e)
	}
	client.ServerName = "10.9.8.30"
	c := &http.Client{Transport: &http.Transport{TLSClientConfig: client}, Timeout: time.Second}
	r, e := c.Get(s.URL)
	if e != nil || r.StatusCode != 204 {
		t.Fatalf("valid client: %v", e)
	}
	r.Body.Close()
	raw, _ := os.ReadFile(f("allowed-serial"))
	os.WriteFile(f("allowed-serial"), []byte("000"+strings.ToUpper(strings.TrimSpace(string(raw)))+"\n"), 0600)
	r, e = c.Get(s.URL)
	if e != nil || r.StatusCode != 204 {
		t.Fatalf("serial normalization: %v", e)
	}
	r.Body.Close()
	noCert := client.Clone()
	noCert.Certificates = nil
	if _, e = (&http.Client{Transport: &http.Transport{TLSClientConfig: noCert}, Timeout: time.Second}).Get(s.URL); e == nil {
		t.Fatal("missing certificate admitted")
	}
	wrongCA := client.Clone()
	wrongCA.RootCAs = x509.NewCertPool()
	if _, e = (&http.Client{Transport: &http.Transport{TLSClientConfig: wrongCA}, Timeout: time.Second}).Get(s.URL); e == nil {
		t.Fatal("untrusted server admitted")
	}
	if e = os.WriteFile(f("allowed-serial"), []byte("revoked\n"), 0600); e != nil {
		t.Fatal(e)
	}
	r, e = c.Get(s.URL)
	if e != nil || r.StatusCode != 403 {
		t.Fatalf("reused connection not revoked: %v", e)
	}
	r.Body.Close()
}
func TestPrivateTargetsAndPorts(t *testing.T) {
	for _, s := range []string{"127.0.0.1", "10.9.8.30", "192.168.1.162", "100.64.0.1", "169.254.169.254", "::1", "fc00::1", "fe80::1", "192.0.2.1", "0.1.2.3", "64:ff9b::7f00:1", "2002:7f00:1::1"} {
		if !privateIP(net.ParseIP(s)) {
			t.Fatal("not private", s)
		}
	}
	for _, s := range []string{"1.1.1.1", "2606:4700:4700::1111"} {
		if privateIP(net.ParseIP(s)) {
			t.Fatal("public blocked", s)
		}
	}
	for _, a := range []string{"127.0.0.1:80", "10.9.8.30:443", "1.1.1.1:3425"} {
		if c, e := publicDial(context.Background(), "tcp", a); e == nil {
			c.Close()
			t.Fatal("forbidden dial", a)
		}
	}
}
func TestNoCertificateOverwrite(t *testing.T) {
	d := t.TempDir()
	if e := generate(d); e != nil {
		t.Fatal(e)
	}
	if e := generate(d); e == nil {
		t.Fatal("overwrote existing CA")
	}
}
func TestInvalidCertificateConfigFails(t *testing.T) {
	if _, e := config("missing", "missing", "missing", true, "missing"); e == nil {
		t.Fatal("fail open")
	}
	if e := admitted([]*x509.Certificate{}, "missing"); e == nil {
		t.Fatal("missing policy accepted")
	}
	_ = tls.VersionTLS12
}

func TestDNS64EmbeddedAddresses(t *testing.T) {
	for _, s := range []string{"64:ff9b::a09:81e", "64:ff9b::7f00:1", "64:ff9b::a9fe:a9fe", "64:ff9b::6440:1", "64:ff9b:1::101:101"} {
		if !privateIP(net.ParseIP(s)) {
			t.Fatal("unsafe translated target admitted", s)
		}
	}
	for _, s := range []string{"64:ff9b::2275:3b51", "64:ff9b::101:101"} {
		if privateIP(net.ParseIP(s)) {
			t.Fatal("public DNS64 target refused", s)
		}
	}
}
func fakeLookup(ips ...string) lookupIPs {
	return func(ctx context.Context, host string) ([]net.IPAddr, error) {
		out := []net.IPAddr{}
		for _, ip := range ips {
			out = append(out, net.IPAddr{IP: net.ParseIP(ip)})
		}
		return out, nil
	}
}
func TestMixedDNSPinsOnlyApprovedPublicIP(t *testing.T) {
	dialled := make(chan string, 4)
	dial := func(ctx context.Context, network, address string) (net.Conn, error) {
		dialled <- address
		a, b := net.Pipe()
		go func() { defer b.Close(); b.Write([]byte("x")) }()
		return a, nil
	}
	c, e := publicDialWith(context.Background(), "mixed.invalid:443", fakeLookup("10.9.8.30", "127.0.0.1", "34.117.59.81"), dial)
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	buf := make([]byte, 1)
	if _, e = c.Read(buf); e != nil || buf[0] != 'x' {
		t.Fatal("working public connection lost", e)
	}
	if got := <-dialled; got != "34.117.59.81:443" {
		t.Fatal("unapproved or unresolved target dialled", got)
	}
	select {
	case extra := <-dialled:
		t.Fatal("private fallback attempted", extra)
	default:
	}
}
func TestPublicDNS64OnlyRoute(t *testing.T) {
	dialled := ""
	var peer net.Conn
	dial := func(ctx context.Context, network, address string) (net.Conn, error) {
		dialled = address
		c, p := net.Pipe()
		peer = p
		return c, nil
	}
	c, e := publicDialWith(context.Background(), "v6only.invalid:443", fakeLookup("64:ff9b::2275:3b51"), dial)
	if e != nil {
		t.Fatal(e)
	}
	c.Close()
	peer.Close()
	if dialled != "[64:ff9b::2275:3b51]:443" {
		t.Fatal("NAT64 route not retained", dialled)
	}
}
func TestBlockedAddressNeverDialled(t *testing.T) {
	called := false
	_, e := publicDialWith(context.Background(), "private.invalid:443", fakeLookup("10.9.8.30", "64:ff9b::7f00:1"), func(context.Context, string, string) (net.Conn, error) { called = true; return nil, context.Canceled })
	if e == nil || called {
		t.Fatal("unsafe target dialled")
	}
}
func TestDeadFamilyDoesNotDelayWorkingFamily(t *testing.T) {
	cancelled := make(chan struct{})
	var peer net.Conn
	dial := func(ctx context.Context, network, address string) (net.Conn, error) {
		if address == "1.1.1.1:443" {
			<-ctx.Done()
			close(cancelled)
			return nil, ctx.Err()
		}
		c, p := net.Pipe()
		peer = p
		return c, nil
	}
	start := time.Now()
	c, e := publicDialWith(context.Background(), "family.invalid:443", fakeLookup("1.1.1.1", "2606:4700:4700::1111"), dial)
	if e != nil {
		t.Fatal(e)
	}
	c.Close()
	peer.Close()
	if time.Since(start) > 2*time.Second {
		t.Fatal("working family blocked by dead family")
	}
	select {
	case <-cancelled:
	case <-time.After(time.Second):
		t.Fatal("losing attempt not cancelled")
	}
}

func TestCONNECTPolicyFailureIsExplicit(t *testing.T) {
	for _, host := range []string{"10.9.8.30:3425", "127.0.0.1:443", "[64:ff9b::a09:81e]:443"} {
		r := httptest.NewRequest("CONNECT", "http://unused.invalid", nil)
		r.Host = host
		w := httptest.NewRecorder()
		egress().ServeHTTP(w, r)
		if w.Code != http.StatusForbidden || w.Header().Get("X-CN-Agent-Egress-Error") != "egress_target_refused" {
			t.Fatalf("ambiguous refusal for %s: %d", host, w.Code)
		}
	}
}

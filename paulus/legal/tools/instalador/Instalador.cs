// O instalador do PAULUS (e o desinstalador: o mesmo programa).
//
// Uma janela so, desenhada aqui, no desenho aprovado das telas revisadas
// (Instalador.dc.html, 07/10/2026): 720 x 540 a 96 DPI, as cores do site
// (site/assets/site.css) nos dois temas, a lateral com PAVLVS e as etapas, e
// os elementos no padrao de 07/10 (botao principal de moldura dupla com 32 px,
// campo de 36 px, cantos 8/12/16). A serifa (Garamond) so em PAVLVS e no
// titulo de cada tela; o resto em Manrope, com o kerning da fonte, como no
// navegador. Quatro etapas: Boas-vindas, Local, Instalacao, Concluido. Tudo
// que e escolha (modelo de IA, escritorio, dados) fica para o assistente de
// configuracao, dentro do app.
//
// O que ele faz: copia o programa para %LOCALAPPDATA%\Programs\PAULUS (sem
// administrador), cria os atalhos, registra o desinstalador no Windows e,
// se faltar, baixa e instala o Ollama (o motor da IA local) e o WebView2 (a
// janela do programa). Os dados do escritorio ficam fora dali, em
// %LOCALAPPDATA%\PAULUS: atualizar troca o programa e nao toca neles.
//
// O programa vem dentro deste .exe: tools\instalador\construir.py compila
// este arquivo e emenda no fim o 7zr.exe (7-Zip, LGPL) e o programa em .7z,
// com um rodape de 40 bytes que diz onde cada parte comeca. Desinstalar.exe
// e este mesmo programa sem as partes emendadas.
//
// Sem nada para instalar e sem custo: compilado com o csc.exe do .NET
// Framework 4, que ja vem no Windows 10 e 11. Por isso C# 5 (sem $"...").

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.IO;
using System.Net;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

static class Programa
{
    public static string[] Args = new string[0];
    public static bool Silencioso;

    public static bool Tem(string opcao)
    {
        foreach (string a in Args)
            if (string.Equals(a, opcao, StringComparison.OrdinalIgnoreCase)) return true;
        return false;
    }

    public static string Valor(string opcao)
    {
        string prefixo = opcao + "=";
        foreach (string a in Args)
            if (a.StartsWith(prefixo, StringComparison.OrdinalIgnoreCase)) return a.Substring(prefixo.Length).Trim('"');
        return null;
    }

    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();

    [STAThread]
    static int Main(string[] args)
    {
        Args = args;
        Silencioso = Tem("/silencioso") || Tem("/verysilent");
        try { ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072; } catch (Exception) { }
        // A conferencia da assinatura, sozinha (tests/test_r7_assistente.py e
        // quem publica): 0 se o arquivo e da Cloudflare, 3 se nao e.
        string conferir = Valor("/conferir-assinatura");
        if (conferir != null)
        {
            string motivo;
            bool ok = Assinatura.DaCloudflare(conferir, out motivo);
            Registro.Linha("conferir assinatura de " + conferir + ": " + (ok ? "Cloudflare" : motivo));
            return ok ? 0 : 3;
        }

        string eu = Application.ExecutablePath;
        bool desinstalar = Tem("/desinstalar") || Path.GetFileName(eu).StartsWith("Desinstalar", StringComparison.OrdinalIgnoreCase);

        if (desinstalar && !Tem("/relancado"))
        {
            // O desinstalador mora na pasta que ele apaga: roda de uma copia
            // na pasta temporaria, e esta sai logo.
            string pasta = Valor("/pasta") ?? Path.GetDirectoryName(eu);
            string copia = Path.Combine(Path.GetTempPath(), "PAULUS-desinstalar-" + Guid.NewGuid().ToString("N").Substring(0, 8) + ".exe");
            try
            {
                File.WriteAllBytes(copia, Pacote.LerStub(eu));
                var resto = new StringBuilder("/desinstalar /relancado \"/pasta=" + pasta + "\" /pai=" + Process.GetCurrentProcess().Id);
                foreach (string a in args)
                    if (!a.StartsWith("/pasta=", StringComparison.OrdinalIgnoreCase) && !string.Equals(a, "/desinstalar", StringComparison.OrdinalIgnoreCase))
                        resto.Append(" \"" + a + "\"");
                // Sai logo: a copia espera este processo fechar para poder apagar o
                // Desinstalar.exe da pasta (o registro do que fez fica no log).
                Process.Start(new ProcessStartInfo(copia, resto.ToString()) { UseShellExecute = false });
                return 0;
            }
            catch (Exception e)
            {
                Registro.Linha("nao consegui copiar o desinstalador: " + e.Message);
                // Segue daqui mesmo: a pasta so nao sai inteira.
            }
        }

        if (Tem("/relancado"))
        {
            int pai;
            if (int.TryParse(Valor("/pai") ?? "", out pai))
            {
                try { Process.GetProcessById(pai).WaitForExit(15000); } catch (Exception) { }
            }
        }
        if (Silencioso) return desinstalar ? Motor.DesinstalarCalado() : Motor.InstalarCalado();

        try { SetProcessDPIAware(); } catch (Exception) { }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        if (!desinstalar && !Pacote.TemPrograma(eu))
        {
            MessageBox.Show("Este arquivo não traz o programa do Paulus. Baixe o instalador de novo em paulus.ia.br.",
                "Paulus", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        Fontes.Carregar();
        Application.Run(new Janela(desinstalar));
        Fontes.Liberar();
        if (desinstalar) Motor.ApagarEstaCopiaDepois();
        return 0;
    }
}

// ---------------------------------------------------------------- assinatura

// A conferencia do cloudflared baixado, antes de ele ser usado: a assinatura
// Authenticode tem de ser valida para o Windows (WinVerifyTrust) E o assinante
// tem de ser a Cloudflare. So a primeira parte aceitaria qualquer programa
// assinado por qualquer empresa; so a segunda leria um nome que qualquer um
// escreve num certificado falso.
static class Assinatura
{
    [DllImport("wintrust.dll", ExactSpelling = true, CharSet = CharSet.Unicode)]
    static extern int WinVerifyTrust(IntPtr hwnd, [MarshalAs(UnmanagedType.LPStruct)] Guid acao, IntPtr dados);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct ArquivoConfiavel   // WINTRUST_FILE_INFO
    {
        public uint cbStruct;
        [MarshalAs(UnmanagedType.LPWStr)] public string pcwszFilePath;
        public IntPtr hFile;
        public IntPtr pgKnownSubject;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct DadosDeConfianca   // WINTRUST_DATA
    {
        public uint cbStruct;
        public IntPtr pPolicyCallbackData, pSIPClientData;
        public uint dwUIChoice, fdwRevocationChecks, dwUnionChoice;
        public IntPtr pFile;
        public uint dwStateAction;
        public IntPtr hWVTStateData, pwszURLReference;
        public uint dwProvFlags, dwUIContext;
        public IntPtr pSignatureSettings;
    }

    // WINTRUST_ACTION_GENERIC_VERIFY_V2: a politica de assinatura de codigo do Windows.
    static readonly Guid VERIFICAR = new Guid("00AAC56B-CD44-11d0-8CC2-00C04FC295EE");

    public static bool DaCloudflare(string arquivo, out string motivo)
    {
        motivo = "";
        if (!File.Exists(arquivo)) { motivo = "o arquivo não existe"; return false; }
        var info = new ArquivoConfiavel();
        info.cbStruct = (uint)Marshal.SizeOf(typeof(ArquivoConfiavel));
        info.pcwszFilePath = arquivo;
        IntPtr pInfo = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(ArquivoConfiavel)));
        IntPtr pDados = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(DadosDeConfianca)));
        try
        {
            Marshal.StructureToPtr(info, pInfo, false);
            var d = new DadosDeConfianca();
            d.cbStruct = (uint)Marshal.SizeOf(typeof(DadosDeConfianca));
            d.dwUIChoice = 2;          // WTD_UI_NONE
            d.fdwRevocationChecks = 0; // WTD_REVOKE_NONE: a revogacao pede rede, e a cadeia ja e conferida
            d.dwUnionChoice = 1;       // WTD_CHOICE_FILE
            d.pFile = pInfo;
            d.dwProvFlags = 0x10;      // WTD_REVOCATION_CHECK_NONE
            Marshal.StructureToPtr(d, pDados, false);
            int r = WinVerifyTrust(new IntPtr(-1), VERIFICAR, pDados);
            if (r != 0) { motivo = "assinatura digital inválida ou ausente (0x" + r.ToString("X8") + ")"; return false; }
        }
        finally
        {
            Marshal.DestroyStructure(pInfo, typeof(ArquivoConfiavel));
            Marshal.FreeHGlobal(pInfo);
            Marshal.FreeHGlobal(pDados);
        }
        try
        {
            var cert = System.Security.Cryptography.X509Certificates.X509Certificate.CreateFromSignedFile(arquivo);
            string assinante = cert.Subject ?? "";
            if (assinante.IndexOf("O=\"Cloudflare, Inc.\"", StringComparison.Ordinal) < 0 &&
                assinante.IndexOf("CN=\"Cloudflare, Inc.\"", StringComparison.Ordinal) < 0)
            {
                motivo = "assinado por outro: " + assinante;
                return false;
            }
        }
        catch (Exception e) { motivo = "assinante ilegível: " + e.Message; return false; }
        return true;
    }
}

// ------------------------------------------------------------------ registro

static class Registro
{
    static readonly object trava = new object();
    public static string Arquivo = Path.Combine(Path.GetTempPath(), "PAULUS-instalador.log");

    public static void Linha(string texto)
    {
        lock (trava)
        {
            try { File.AppendAllText(Arquivo, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + texto + Environment.NewLine, Encoding.UTF8); }
            catch (Exception) { }
        }
    }
}

// ------------------------------------------------------------------- o pacote

static class Pacote
{
    // Rodape: tamanho do stub, do 7zr.exe, do .7z, do programa instalado
    // (bytes) e a marca.
    const long MARCA = 0x323053554C554150; // os bytes "PAULUS02"

    public static bool Ler(string exe, out long stub, out long tam7zr, out long tam7z, out long instalado)
    {
        stub = tam7zr = tam7z = instalado = 0;
        try
        {
            using (var f = new FileStream(exe, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            {
                if (f.Length < 40) return false;
                f.Seek(-40, SeekOrigin.End);
                var r = new BinaryReader(f);
                stub = r.ReadInt64(); tam7zr = r.ReadInt64(); tam7z = r.ReadInt64(); instalado = r.ReadInt64();
                return r.ReadInt64() == MARCA && stub > 0 && stub + tam7zr + tam7z + 40 == f.Length;
            }
        }
        catch (Exception) { return false; }
    }

    public static bool TemPrograma(string exe)
    {
        long a, b, c, d;
        return Ler(exe, out a, out b, out c, out d);
    }

    public static long TamanhoInstalado()
    {
        long a, b, c, d;
        return Ler(Application.ExecutablePath, out a, out b, out c, out d) ? d : 0;
    }

    /* O proprio programa, sem as partes emendadas: vira o Desinstalar.exe. */
    public static byte[] LerStub(string exe)
    {
        long stub, a, b, c;
        byte[] tudo = File.ReadAllBytes(exe);
        if (!Ler(exe, out stub, out a, out b, out c)) return tudo;
        byte[] so = new byte[stub];
        Array.Copy(tudo, so, stub);
        return so;
    }

    public static void Copiar(string exe, long inicio, long tamanho, string destino)
    {
        using (var f = new FileStream(exe, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        using (var o = new FileStream(destino, FileMode.Create, FileAccess.Write))
        {
            f.Seek(inicio, SeekOrigin.Begin);
            byte[] buf = new byte[1 << 20];
            long falta = tamanho;
            while (falta > 0)
            {
                int n = f.Read(buf, 0, (int)Math.Min(buf.Length, falta));
                if (n <= 0) throw new IOException("o instalador está incompleto (baixe de novo)");
                o.Write(buf, 0, n);
                falta -= n;
            }
        }
    }
}

// --------------------------------------------------------------- o que faz

class Opcoes
{
    public string Pasta;
    public bool AtalhoMesa = true, MenuIniciar = true, Explorer = false, Ollama = true, Tunel = false;
}

class Andamento
{
    public volatile bool Cancelar;
    // O programa novo ja esta inteiro e registrado: cancelar dali em diante
    // so para os downloads (Ollama, WebView2).
    public volatile bool ProgramaPronto;
    public Action<double, string> Relatar = delegate { };
    public string Aviso = "";
}

class Instalado
{
    public string Pasta, Versao;
    public bool Inno;
}

class CanceladoException : Exception
{
    public CanceladoException() : base("cancelado") { }
}

class PastaPresaException : IOException
{
    public PastaPresaException(string mensagem) : base(mensagem) { }
}

static class Motor
{
    public const string CHAVE = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\PAULUS";
    public const string CHAVE_INNO = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\{8C3E6A2B-5F1D-4C9A-9B7E-2A4D6F8B0C11}_is1";
    public static readonly string[] TIPOS = { ".pdf", ".docx", ".txt", ".md", ".xlsx" };
    const string URL_OLLAMA = "https://ollama.com/download/OllamaSetup.exe";
    const string URL_WEBVIEW2 = "https://go.microsoft.com/fwlink/p/?LinkId=2124703";
    // O cloudflared do acesso de fora (docs/acesso-de-fora.md): versao FIXA,
    // trocada a mao por quem publica - nada de "a mais nova" baixada no
    // escuro. E o arquivo so e usado depois de conferida a assinatura da
    // Cloudflare (Assinatura.DaCloudflare).
    public const string VERSAO_CLOUDFLARED = "2026.9.3";
    const string URL_CLOUDFLARED = "https://github.com/cloudflare/cloudflared/releases/download/" + VERSAO_CLOUDFLARED + "/cloudflared-windows-amd64.exe";

    public static string LocalAppData { get { return Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData); } }
    // PAULUS_CASA troca a pasta dos dados e modelos (so para testes: o
    // PAULUS.exe instalado usa sempre %LOCALAPPDATA%\PAULUS).
    public static string Casa
    {
        get
        {
            string outra = Environment.GetEnvironmentVariable("PAULUS_CASA");
            return string.IsNullOrEmpty(outra) ? Path.Combine(LocalAppData, "PAULUS") : outra;
        }
    }
    public static string PastaPadrao { get { return Path.Combine(LocalAppData, "Programs", "PAULUS"); } }
    public static string OllamaExe { get { return Path.Combine(LocalAppData, "Programs", "Ollama", "ollama.exe"); } }
    // Sem administrador, como o resto; o PAULUS procura aqui primeiro (src/acesso/tunel.py).
    public static string PastaCloudflared { get { return Path.Combine(LocalAppData, "Programs", "PAULUS-cloudflared"); } }
    public static string CloudflaredExe { get { return Path.Combine(PastaCloudflared, "cloudflared.exe"); } }

    /* A entrada no Windows de cada pasta: a pasta padrao usa "PAULUS"; outra
       pasta (um teste, um segundo PAULUS) ganha a sua, "PAULUS-<8 letras>".
       Com um nome so, instalar em outra pasta sobrescrevia a entrada da
       instalacao de verdade, e desinstalar essa outra a apagava. */
    public static string ChaveDe(string pasta)
    {
        if (MesmaPasta(pasta, PastaPadrao)) return CHAVE;
        using (var sha = System.Security.Cryptography.SHA1.Create())
        {
            byte[] h = sha.ComputeHash(Encoding.UTF8.GetBytes(Normal(pasta).ToLowerInvariant()));
            return CHAVE + "-" + BitConverter.ToString(h, 0, 4).Replace("-", "").ToLowerInvariant();
        }
    }

    public static Instalado LerInstalado()
    {
        foreach (string chave in new[] { CHAVE, CHAVE_INNO })
        {
            using (RegistryKey k = Registry.CurrentUser.OpenSubKey(chave))
            {
                if (k == null) continue;
                string pasta = (k.GetValue("InstallLocation") as string ?? "").TrimEnd('\\');
                if (pasta == "" || !Directory.Exists(pasta)) continue;
                var i = new Instalado();
                i.Pasta = pasta;
                i.Versao = k.GetValue("DisplayVersion") as string ?? "";
                i.Inno = chave == CHAVE_INNO;
                return i;
            }
        }
        // Sem registro (apagado, ou instalacao copiada): a pasta padrao com o
        // programa dentro tambem conta como instalado.
        if (ParecePaulus(PastaPadrao))
        {
            var i = new Instalado();
            i.Pasta = PastaPadrao;
            i.Versao = VersaoNaPasta(PastaPadrao);
            i.Inno = File.Exists(Path.Combine(PastaPadrao, "unins000.exe"));
            return i;
        }
        return null;
    }

    public static bool ParecePaulus(string pasta)
    {
        return File.Exists(Path.Combine(pasta, "PAULUS.exe")) && File.Exists(Path.Combine(pasta, "app", "src", "desktop.py"));
    }

    /* A versao do programa numa pasta, lida do proprio codigo (src/versao.py). */
    public static string VersaoNaPasta(string pasta)
    {
        try
        {
            foreach (string l in File.ReadAllLines(Path.Combine(pasta, "app", "src", "versao.py")))
            {
                Match m = Regex.Match(l, "^VERSAO\\s*=\\s*[\"']([^\"']+)");
                if (m.Success) return m.Groups[1].Value;
            }
        }
        catch (Exception) { }
        return "";
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    static extern uint GetLongPathName(string curto, StringBuilder longo, uint tamanho);

    /* O mesmo caminho o Windows escreve de dois jeitos: C:\Users\MATHEU~1 e
       C:\Users\MATHEUSUENER. Comparar sem isto deixava sobrar o que era
       desta pasta (e podia tocar o que nao era). */
    public static string Normal(string caminho)
    {
        if (string.IsNullOrEmpty(caminho)) return "";
        try
        {
            string cheio = Path.GetFullPath(caminho.Trim().Trim('"'));
            var sb = new StringBuilder(1024);
            // So existe no disco quem tem forma longa; o resto fica como veio.
            string existe = cheio;
            string resto = "";
            while (!string.IsNullOrEmpty(existe) && !File.Exists(existe) && !Directory.Exists(existe))
            {
                resto = "\\" + Path.GetFileName(existe) + resto;
                existe = Path.GetDirectoryName(existe);
            }
            if (!string.IsNullOrEmpty(existe) && GetLongPathName(existe, sb, (uint)sb.Capacity) > 0) cheio = sb.ToString() + resto;
            return cheio.TrimEnd('\\');
        }
        catch (Exception) { return caminho; }
    }

    static bool MesmaPasta(string a, string b)
    {
        if (string.IsNullOrEmpty(a) || string.IsNullOrEmpty(b)) return false;
        return string.Equals(Normal(a), Normal(b), StringComparison.OrdinalIgnoreCase);
    }

    static bool Dentro(string caminho, string pasta)
    {
        if (string.IsNullOrEmpty(caminho) || string.IsNullOrEmpty(pasta)) return false;
        return Normal(caminho).StartsWith(Normal(pasta) + "\\", StringComparison.OrdinalIgnoreCase);
    }

    /* O PAULUS.exe que o comando do menu do Explorer abre. */
    static string ExeDoComando(string comando)
    {
        if (string.IsNullOrEmpty(comando)) return "";
        if (comando.StartsWith("\"")) { int fim = comando.IndexOf('"', 1); return fim > 1 ? comando.Substring(1, fim - 1) : ""; }
        int espaco = comando.IndexOf(' ');
        return espaco > 0 ? comando.Substring(0, espaco) : comando;
    }

    /* A chave de desinstalacao so e desta pasta se o InstallLocation dela for esta pasta. */
    static bool ChaveDaPasta(string chave, string pasta)
    {
        using (RegistryKey k = Registry.CurrentUser.OpenSubKey(chave))
            return k != null && MesmaPasta(k.GetValue("InstallLocation") as string, pasta);
    }

    static void ApagarChaveDaPasta(string chave, string pasta)
    {
        if (!ChaveDaPasta(chave, pasta)) return;
        try { Registry.CurrentUser.DeleteSubKeyTree(chave, false); } catch (Exception) { }
    }

    /* Para onde um atalho aponta ("" se nao der para ler). */
    static string AlvoDoAtalho(string lnk)
    {
        if (!File.Exists(lnk)) return "";
        try
        {
            Type t = Type.GetTypeFromProgID("WScript.Shell");
            object shell = Activator.CreateInstance(t);
            object a = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { lnk });
            string alvo = (string)a.GetType().InvokeMember("TargetPath", BindingFlags.GetProperty, null, a, null);
            Marshal.FinalReleaseComObject(a);
            Marshal.FinalReleaseComObject(shell);
            return alvo ?? "";
        }
        catch (Exception) { return ""; }
    }

    /* So apaga o atalho se ele e desta instalacao: o de outra pasta fica. */
    public static bool AtalhoDaPasta(string lnk, string pasta)
    {
        return Dentro(AlvoDoAtalho(lnk), pasta);
    }

    public static string AtalhoDaMesa { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "PAULUS.lnk"); } }
    public static string AtalhoDoIniciar { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "PAULUS.lnk"); } }

    /* Atualizar mantem o que a pessoa escolheu da outra vez: os atalhos que
       existem para esta pasta, o menu do Explorer, e nada de Ollama novo. */
    public static void OpcoesDeQuemAtualiza(Opcoes o)
    {
        o.AtalhoMesa = AtalhoDaPasta(AtalhoDaMesa, o.Pasta);
        o.MenuIniciar = AtalhoDaPasta(AtalhoDoIniciar, o.Pasta) || !File.Exists(AtalhoDoIniciar);
        o.Explorer = MenuDoExplorerLigado(o.Pasta);
        o.Ollama = false;
        // O cloudflared vem sempre que falta, como o Ollama: instalar o
        // programa nao liga nada - o acesso a distancia fica desligado ate o
        // titular ligar no assistente de configuracao.
        o.Tunel = !CloudflaredPresente();
    }

    static void ApagarAtalhoDaPasta(string lnk, string pasta)
    {
        if (Dentro(AlvoDoAtalho(lnk), pasta)) Apagar(lnk);
    }

    public static bool OllamaPresente()
    {
        if (File.Exists(OllamaExe)) return true;
        string pf = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        if (File.Exists(Path.Combine(pf, "Ollama", "ollama.exe"))) return true;
        foreach (string p in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';'))
        {
            try { if (p.Trim() != "" && File.Exists(Path.Combine(p.Trim(), "ollama.exe"))) return true; }
            catch (Exception) { }
        }
        return false;
    }

    public static bool CloudflaredPresente()
    {
        if (File.Exists(CloudflaredExe)) return true;
        string pf = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        if (File.Exists(Path.Combine(pf, "cloudflared", "cloudflared.exe"))) return true;
        foreach (string p in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';'))
        {
            try { if (p.Trim() != "" && File.Exists(Path.Combine(p.Trim(), "cloudflared.exe"))) return true; }
            catch (Exception) { }
        }
        return false;
    }

    /* O acesso de fora ligado nesta maquina: as preferencias do PAULUS dizem. */
    public static bool AcessoDeForaEmUso()
    {
        try
        {
            string p = Path.Combine(Casa, "dados", "preferencias.json");
            if (!File.Exists(p)) return false;
            return Regex.IsMatch(File.ReadAllText(p), "\"acesso_remoto\"\\s*:\\s*\\{[^}]*\"ligado\"\\s*:\\s*true");
        }
        catch (Exception) { return false; }
    }

    /* O tamanho do cloudflared, para a tela dizer quanto vem. */
    public static long TamanhoDoCloudflared()
    {
        try
        {
            var req = (HttpWebRequest)WebRequest.Create(URL_CLOUDFLARED);
            req.Method = "HEAD";
            req.Timeout = 6000;
            req.UserAgent = "PAULUS-instalador";
            using (var r = (HttpWebResponse)req.GetResponse()) return r.ContentLength;
        }
        catch (Exception) { return 0; }
    }

    /* O cloudflared do PAULUS rodando (o tunel ligado) prende a pasta: sai. */
    static void FecharCloudflared()
    {
        foreach (Process p in Process.GetProcessesByName("cloudflared"))
        {
            try
            {
                if (p.MainModule.FileName.StartsWith(PastaCloudflared + "\\", StringComparison.OrdinalIgnoreCase))
                { p.Kill(); p.WaitForExit(5000); }
            }
            catch (Exception) { }
        }
    }

    static string AcharOllama()
    {
        if (File.Exists(OllamaExe)) return OllamaExe;
        string pf = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Ollama", "ollama.exe");
        return File.Exists(pf) ? pf : null;
    }

    public static bool WebView2Presente()
    {
        const string id = @"\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
        string[] lugares = { @"SOFTWARE\WOW6432Node" + id, @"SOFTWARE" + id };
        foreach (string l in lugares)
        {
            foreach (RegistryKey raiz in new[] { Registry.LocalMachine, Registry.CurrentUser })
            {
                using (RegistryKey k = raiz.OpenSubKey(l))
                {
                    if (k == null) continue;
                    string v = k.GetValue("pv") as string;
                    if (!string.IsNullOrEmpty(v) && v != "0.0.0.0") return true;
                }
            }
        }
        return false;
    }

    /* O tamanho do instalador do Ollama, para a tela dizer quanto vem. */
    public static long TamanhoDoOllama()
    {
        try
        {
            var req = (HttpWebRequest)WebRequest.Create(URL_OLLAMA);
            req.Method = "HEAD";
            req.Timeout = 6000;
            req.UserAgent = "PAULUS-instalador";
            using (var r = (HttpWebResponse)req.GetResponse()) return r.ContentLength;
        }
        catch (Exception) { return 0; }
    }

    /* Os processos do PAULUS que rodam desta pasta (o python dele). */
    public static List<Process> Abertos(string pasta)
    {
        var lista = new List<Process>();
        string py = Path.Combine(pasta, "python") + "\\";
        foreach (string nome in new[] { "pythonw", "python" })
        {
            foreach (Process p in Process.GetProcessesByName(nome))
            {
                try
                {
                    if (p.MainModule.FileName.StartsWith(py, StringComparison.OrdinalIgnoreCase)) lista.Add(p);
                }
                catch (Exception) { }
            }
        }
        return lista;
    }

    public static void Fechar(string pasta)
    {
        foreach (Process p in Abertos(pasta))
        {
            try { p.Kill(); p.WaitForExit(8000); } catch (Exception) { }
        }
    }

    // O Ollama que o PAULUS de antes ligou pode estar rodando com a pasta do
    // programa como pasta de trabalho: enquanto ele roda, o Windows nao deixa
    // mover nem apagar a pasta. Quando a pasta esta presa, ele e fechado e
    // ligado de novo no fim, da pasta dele.
    static bool ollamaFechado;

    static bool FecharOllama()
    {
        bool fechou = false;
        foreach (string nome in new[] { "ollama", "ollama app" })
        {
            foreach (Process p in Process.GetProcessesByName(nome))
            {
                try { p.Kill(); p.WaitForExit(5000); fechou = true; } catch (Exception) { }
            }
        }
        if (fechou) { ollamaFechado = true; Registro.Linha("fechei o Ollama, que prendia a pasta"); }
        return fechou;
    }

    public static void ReligarOllama()
    {
        if (!ollamaFechado) return;
        ollamaFechado = false;
        string exe = AcharOllama();
        if (exe == null) return;
        try
        {
            Process.Start(new ProcessStartInfo(exe, "serve")
            { UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = Path.GetDirectoryName(exe) });
        }
        catch (Exception e) { Registro.Linha("nao religuei o Ollama: " + e.Message); }
    }

    /* Esvazia uma pasta presa sem apagar a pasta em si (que e o que o Windows
       nao deixa): o conteudo sai, e o novo entra nela. */
    static void Esvaziar(string pasta)
    {
        foreach (string item in Directory.GetFileSystemEntries(pasta))
        {
            Apagar(item);
            if (Directory.Exists(item) || File.Exists(item))
                throw new IOException("Um arquivo em " + pasta + " está em uso por outro programa e não pôde ser trocado: " + item +
                                      ". Reinicie o computador e rode o instalador de novo.");
        }
    }

    public static string PodeEscrever(string pasta)
    {
        try
        {
            Directory.CreateDirectory(pasta);
            string teste = Path.Combine(pasta, ".paulus-teste");
            File.WriteAllText(teste, "ok");
            File.Delete(teste);
        }
        catch (Exception e)
        {
            return "Não dá para instalar nessa pasta: " + e.Message + " Escolha outra, dentro da sua pasta de usuário.";
        }
        try
        {
            long livre = new DriveInfo(Path.GetPathRoot(Path.GetFullPath(pasta))).AvailableFreeSpace;
            long precisa = Pacote.TamanhoInstalado() + (200L << 20);
            if (livre < precisa)
                return "Falta espaço em disco: precisa de " + Janela.MB(precisa) + " e há " + Janela.MB(livre) + " livres.";
        }
        catch (Exception) { }
        return null;
    }

    // ------------------------------------------------------------- instalar

    public static void Instalar(Opcoes o, Andamento a)
    {
        string pasta = o.Pasta;
        string eu = Application.ExecutablePath;
        long stub, tam7zr, tam7z, inst;
        if (!Pacote.Ler(eu, out stub, out tam7zr, out tam7z, out inst))
            throw new IOException("o instalador está incompleto (baixe de novo)");
        bool baixarOllama = o.Ollama && !OllamaPresente();
        bool baixarWebView = !WebView2Presente();
        bool baixarTunel = o.Tunel && !CloudflaredPresente();
        double fimExtrair = baixarOllama ? 40 : (baixarWebView ? 70 : (baixarTunel ? 80 : 85));

        Registro.Linha("instalando em " + pasta + (baixarOllama ? " (com Ollama)" : "") + (baixarWebView ? " (com WebView2)" : "") +
                       (baixarTunel ? " (com cloudflared)" : ""));
        a.Relatar(0, "Preparando…");
        Fechar(pasta);
        Directory.CreateDirectory(pasta);
        string temp = Path.Combine(Path.GetTempPath(), "PAULUS-instalar-" + Guid.NewGuid().ToString("N").Substring(0, 8));
        Directory.CreateDirectory(temp);
        // O programa de antes fica guardado ate o novo estar inteiro: cancelar
        // ou falhar no meio devolve ele.
        var guardados = new List<string[]>();
        bool extraiu = false;
        try
        {
            foreach (string nome in new[] { "app", "python", "PAULUS.exe", "Desinstalar.exe" })
            {
                string atual = Path.Combine(pasta, nome), antigo = atual + ".antigo";
                Apagar(antigo);
                if (Directory.Exists(atual) || File.Exists(atual))
                {
                    try
                    {
                        Mover(atual, antigo);
                        guardados.Add(new[] { atual, antigo });
                    }
                    catch (PastaPresaException)
                    {
                        // Presa mesmo depois de fechar o Ollama: nao da para guardar
                        // a versao antiga; o conteudo sai e o novo entra no lugar.
                        if (!Directory.Exists(atual)) throw;
                        Registro.Linha("pasta presa, instalando no lugar: " + atual);
                        Esvaziar(atual);
                    }
                }
            }

            a.Relatar(1, "Extraindo arquivos…");
            extraiu = true;
            string z7 = Path.Combine(temp, "7zr.exe"), pacote = Path.Combine(temp, "paulus.7z");
            Pacote.Copiar(eu, stub, tam7zr, z7);
            Pacote.Copiar(eu, stub + tam7zr, tam7z, pacote);
            Extrair(z7, pacote, pasta, a, 1, fimExtrair);

            a.Relatar(fimExtrair, "Criando atalhos…");
            File.WriteAllBytes(Path.Combine(pasta, "Desinstalar.exe"), Pacote.LerStub(eu));
            RegistrarDesinstalador(pasta, inst);
            string exe = Path.Combine(pasta, "PAULUS.exe");
            string mesa = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "PAULUS.lnk");
            string iniciar = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "PAULUS.lnk");
            if (o.AtalhoMesa) Atalho(mesa, exe, pasta); else ApagarAtalhoDaPasta(mesa, pasta);
            if (o.MenuIniciar) Atalho(iniciar, exe, pasta); else ApagarAtalhoDaPasta(iniciar, pasta);
            if (o.Explorer) MenuDoExplorer(exe); else TirarMenuDoExplorer(pasta);
            Protocolo(exe);
            Directory.CreateDirectory(Path.Combine(Casa, "dados"));
            Directory.CreateDirectory(Path.Combine(Casa, "modelos"));
        }
        catch (Exception)
        {
            // Volta ao que era: o novo sai, o antigo volta. Antes de extrair,
            // o que esta na pasta ainda e o antigo - nada sai.
            if (extraiu)
                foreach (string nome in new[] { "app", "python", "PAULUS.exe", "Desinstalar.exe" })
                    Apagar(Path.Combine(pasta, nome));
            foreach (string[] g in guardados)
            {
                try { Mover(g[1], g[0]); } catch (Exception) { }
            }
            if (guardados.Count == 0) { ApagarChaveDaPasta(ChaveDe(pasta), pasta); TentarApagarVazia(pasta); }
            ApagarTemp(temp);
            ReligarOllama();
            throw;
        }
        foreach (string[] g in guardados) Apagar(g[1]);
        LimparInno(pasta);
        a.ProgramaPronto = true;

        // Daqui em diante o PAULUS ja esta instalado: o que falhar vira aviso.
        double p0 = fimExtrair + 3;
        if (baixarWebView)
        {
            try
            {
                string wv = Path.Combine(temp, "MicrosoftEdgeWebview2Setup.exe");
                Baixar(URL_WEBVIEW2, wv, a, p0, p0 + 4, "Baixando a janela do programa (WebView2)…");
                a.Relatar(p0 + 4, "Instalando a janela do programa (WebView2)…");
                Rodar(wv, "/silent /install", 600000, a);
            }
            catch (CanceladoException) { a.Aviso += "A janela do programa (WebView2) não foi instalada: cancelado. "; }
            catch (Exception e) { a.Aviso += "A janela do programa (WebView2) não foi instalada: " + e.Message + " "; }
            p0 += 6;
        }
        if (baixarTunel)
        {
            try
            {
                string cf = Path.Combine(temp, "cloudflared.exe");
                Baixar(URL_CLOUDFLARED, cf, a, p0, p0 + 3, "Baixando o acesso externo (cloudflared)…");
                a.Relatar(p0 + 3, "Conferindo a assinatura da Cloudflare…");
                // Nunca executar binario que nao passou pela conferencia: sem a
                // assinatura da Cloudflare, o arquivo sai e a instalacao segue.
                string motivo;
                if (!Assinatura.DaCloudflare(cf, out motivo))
                {
                    Apagar(cf);
                    Registro.Linha("cloudflared recusado e apagado: " + motivo);
                    throw new Exception("o arquivo baixado não tem a assinatura da Cloudflare e foi apagado (" + motivo + ").");
                }
                FecharCloudflared();
                Directory.CreateDirectory(PastaCloudflared);
                File.Copy(cf, CloudflaredExe, true);
                Registro.Linha("cloudflared " + VERSAO_CLOUDFLARED + " conferido e instalado em " + PastaCloudflared);
            }
            catch (CanceladoException) { a.Aviso += "O acesso externo (cloudflared) não foi instalado: cancelado. "; }
            catch (Exception e) { a.Aviso += "O acesso externo (cloudflared) não foi instalado: " + e.Message + " "; }
            p0 += 4;
        }
        if (baixarOllama)
        {
            try
            {
                string ol = Path.Combine(temp, "OllamaSetup.exe");
                Baixar(URL_OLLAMA, ol, a, p0, 94, "Baixando o motor de IA local…");
                a.Relatar(95, "Instalando o motor de IA local…");
                Rodar(ol, "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES", 900000, a);
                if (!OllamaPresente()) throw new Exception("o instalador do Ollama terminou sem instalar.");
            }
            catch (CanceladoException) { a.Aviso += "O motor de IA local (Ollama) não foi instalado: você cancelou o download. "; }
            catch (Exception e) { a.Aviso += "O motor de IA local (Ollama) não foi instalado: " + e.Message + " "; }
        }
        a.Relatar(99, "Finalizando…");
        ReligarOllama();
        ApagarTemp(temp);
        Registro.Linha("instalado" + (a.Aviso != "" ? " com aviso: " + a.Aviso : ""));
        a.Relatar(100, "Pronto.");
    }

    static void Extrair(string z7, string pacote, string destino, Andamento a, double de, double ate)
    {
        var info = new ProcessStartInfo(z7, "x \"" + pacote + "\" \"-o" + destino + "\" -y -bsp1 -bso0 -bse2")
        {
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true,
        };
        using (var p = Process.Start(info))
        {
            var erro = new StringBuilder();
            p.ErrorDataReceived += delegate (object s, DataReceivedEventArgs e) { if (e.Data != null) erro.AppendLine(e.Data); };
            p.BeginErrorReadLine();
            var trecho = new StringBuilder();
            var re = new Regex(@"(\d{1,3})%");
            int c;
            while ((c = p.StandardOutput.Read()) >= 0)
            {
                if (a.Cancelar) { try { p.Kill(); } catch (Exception) { } throw new CanceladoException(); }
                char ch = (char)c;
                if (ch == '\b' || ch == '\r' || ch == '\n')
                {
                    Match m = re.Match(trecho.ToString());
                    if (m.Success) a.Relatar(de + (ate - de) * int.Parse(m.Groups[1].Value) / 100.0, "Extraindo arquivos…");
                    trecho.Length = 0;
                }
                else trecho.Append(ch);
            }
            p.WaitForExit();
            if (p.ExitCode != 0) throw new IOException("não consegui extrair o programa (7-Zip " + p.ExitCode + "): " + erro.ToString().Trim());
        }
    }

    static void Baixar(string url, string destino, Andamento a, double de, double ate, string rotulo)
    {
        var req = (HttpWebRequest)WebRequest.Create(url);
        req.UserAgent = "PAULUS-instalador";
        req.Timeout = 30000;
        req.ReadWriteTimeout = 60000;
        using (var r = (HttpWebResponse)req.GetResponse())
        using (var s = r.GetResponseStream())
        using (var o = new FileStream(destino, FileMode.Create, FileAccess.Write))
        {
            long total = r.ContentLength, feito = 0;
            byte[] buf = new byte[1 << 16];
            int n;
            DateTime ultimo = DateTime.MinValue;
            while ((n = s.Read(buf, 0, buf.Length)) > 0)
            {
                if (a.Cancelar) { req.Abort(); throw new CanceladoException(); }
                o.Write(buf, 0, n);
                feito += n;
                if ((DateTime.Now - ultimo).TotalMilliseconds > 200)
                {
                    ultimo = DateTime.Now;
                    double frac = total > 0 ? (double)feito / total : 0;
                    a.Relatar(de + (ate - de) * frac, rotulo + (total > 0 ? " " + Janela.MB(feito) + " de " + Janela.MB(total) : " " + Janela.MB(feito)));
                }
            }
            if (total > 0 && feito < total) throw new IOException("o download parou no meio.");
        }
    }

    static void Rodar(string exe, string argumentos, int limite, Andamento a)
    {
        using (var p = Process.Start(new ProcessStartInfo(exe, argumentos) { UseShellExecute = false, CreateNoWindow = true }))
        {
            if (!p.WaitForExit(limite)) { try { p.Kill(); } catch (Exception) { } throw new Exception("demorou demais."); }
            if (p.ExitCode != 0) throw new Exception("terminou com o código " + p.ExitCode + ".");
        }
    }

    static void RegistrarDesinstalador(string pasta, long instalado)
    {
        using (RegistryKey k = Registry.CurrentUser.CreateSubKey(ChaveDe(pasta)))
        {
            string des = Path.Combine(pasta, "Desinstalar.exe");
            k.SetValue("DisplayName", "PAULUS");
            k.SetValue("DisplayVersion", Versao.Numero);
            k.SetValue("Publisher", "Matheus Uener Silva");
            k.SetValue("URLInfoAbout", "https://paulus.ia.br");
            k.SetValue("DisplayIcon", Path.Combine(pasta, "PAULUS.exe"));
            k.SetValue("InstallLocation", pasta);
            k.SetValue("UninstallString", "\"" + des + "\"");
            k.SetValue("QuietUninstallString", "\"" + des + "\" /silencioso");
            k.SetValue("EstimatedSize", (int)(instalado / 1024), RegistryValueKind.DWord);
            k.SetValue("NoModify", 1, RegistryValueKind.DWord);
            k.SetValue("NoRepair", 1, RegistryValueKind.DWord);
            k.SetValue("InstallDate", DateTime.Now.ToString("yyyyMMdd"));
        }
    }

    /* O instalador de antes (Inno Setup, 0.9.0 de 27/09) deixava o proprio
       desinstalador: sai, para o Windows nao mostrar o PAULUS duas vezes. */
    static void LimparInno(string pasta)
    {
        // So o do Inno DESTA pasta: a chave aponta para ela, ou o
        // desinstalador dele esta nela. Uma instalacao em outra pasta fica.
        bool eraDoInno = ChaveDaPasta(CHAVE_INNO, pasta) || File.Exists(Path.Combine(pasta, "unins000.exe"));
        if (!eraDoInno) return;
        ApagarChaveDaPasta(CHAVE_INNO, pasta);
        Apagar(Path.Combine(pasta, "unins000.exe"));
        Apagar(Path.Combine(pasta, "unins000.dat"));
        string grupo = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "PAULUS");
        if (Directory.Exists(grupo))
        {
            foreach (string lnk in Directory.GetFiles(grupo, "*.lnk")) ApagarAtalhoDaPasta(lnk, pasta);
            TentarApagarVazia(grupo);
        }
        ApagarAtalhoDaPasta(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "PAULUS.lnk"), pasta);
    }

    static void Atalho(string lnk, string alvo, string pasta)
    {
        Type t = Type.GetTypeFromProgID("WScript.Shell");
        object shell = Activator.CreateInstance(t);
        object a = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { lnk });
        Type ta = a.GetType();
        ta.InvokeMember("TargetPath", BindingFlags.SetProperty, null, a, new object[] { alvo });
        ta.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, a, new object[] { pasta });
        ta.InvokeMember("IconLocation", BindingFlags.SetProperty, null, a, new object[] { alvo + ",0" });
        ta.InvokeMember("Description", BindingFlags.SetProperty, null, a, new object[] { "Paulus: assistente jurídico de IA local" });
        ta.InvokeMember("Save", BindingFlags.InvokeMethod, null, a, null);
        Marshal.FinalReleaseComObject(a);
        Marshal.FinalReleaseComObject(shell);
    }

    [DllImport("shell32.dll")] static extern void SHChangeNotify(int evento, int flags, IntPtr a, IntPtr b);

    /* "Perguntar ao Paulus" no botao direito dos arquivos que o programa le (o mesmo
       rotulo de src/menu_explorer.py, que o programa grava quando liga o menu).
       No Windows 11 aparece em "Mostrar mais opções". */
    static void MenuDoExplorer(string exe)
    {
        foreach (string tipo in TIPOS)
        {
            using (RegistryKey k = Registry.CurrentUser.CreateSubKey(@"Software\Classes\SystemFileAssociations\" + tipo + @"\shell\PAULUS.Perguntar"))
            {
                k.SetValue("", "Perguntar ao Paulus");
                k.SetValue("Icon", "\"" + exe + "\",0");
                using (RegistryKey c = k.CreateSubKey("command")) c.SetValue("", "\"" + exe + "\" --perguntar \"%1\"");
            }
        }
        SHChangeNotify(0x08000000, 0, IntPtr.Zero, IntPtr.Zero);
    }

    static void TirarMenuDoExplorer(string pasta)
    {
        foreach (string tipo in TIPOS)
        {
            string chave = @"Software\Classes\SystemFileAssociations\" + tipo + @"\shell\PAULUS.Perguntar";
            try
            {
                string comando = "";
                using (RegistryKey c = Registry.CurrentUser.OpenSubKey(chave + @"\command"))
                    if (c != null) comando = c.GetValue("") as string ?? "";
                if (Dentro(ExeDoComando(comando), pasta))
                    Registry.CurrentUser.DeleteSubKeyTree(chave, false);
            }
            catch (Exception) { }
        }
        SHChangeNotify(0x08000000, 0, IntPtr.Zero, IntPtr.Zero);
    }

    /* O endereco paulus:// (02/10): a pagina de volta do Google abre
       "paulus://voltar" e o navegador pergunta "Abrir PAULUS?" - o PAULUS ja
       aberto vem para a frente (src/desktop.py). Na area do usuario, sem
       pedir administrador. */
    static void Protocolo(string exe)
    {
        using (RegistryKey k = Registry.CurrentUser.CreateSubKey(@"Software\Classes\paulus"))
        {
            k.SetValue("", "URL:PAULUS");
            k.SetValue("URL Protocol", "");
            using (RegistryKey i = k.CreateSubKey("DefaultIcon")) i.SetValue("", "\"" + exe + "\",0");
            using (RegistryKey c = k.CreateSubKey(@"shell\open\command")) c.SetValue("", "\"" + exe + "\" \"%1\"");
        }
    }

    static void TirarProtocolo(string pasta)
    {
        try
        {
            string comando = "";
            using (RegistryKey c = Registry.CurrentUser.OpenSubKey(@"Software\Classes\paulus\shell\open\command"))
                if (c != null) comando = c.GetValue("") as string ?? "";
            if (Dentro(ExeDoComando(comando), pasta))
                Registry.CurrentUser.DeleteSubKeyTree(@"Software\Classes\paulus", false);
        }
        catch (Exception) { }
    }

    /* O menu do Explorer ligado PARA ESTA PASTA (o de outra instalacao nao conta). */
    public static bool MenuDoExplorerLigado(string pasta)
    {
        using (RegistryKey k = Registry.CurrentUser.OpenSubKey(@"Software\Classes\SystemFileAssociations\.pdf\shell\PAULUS.Perguntar\command"))
            return k != null && Dentro(ExeDoComando(k.GetValue("") as string), pasta);
    }

    // ---------------------------------------------------------- desinstalar

    /* Os modelos do Ollama que o PAULUS baixou (src/api.py anota). */
    public static List<string> ModelosDoPaulus()
    {
        var lista = new List<string>();
        string arq = Path.Combine(Casa, "modelos", "ollama_baixados.txt");
        try
        {
            foreach (string l in File.ReadAllLines(arq))
                if (l.Trim() != "" && !lista.Contains(l.Trim())) lista.Add(l.Trim());
        }
        catch (Exception) { }
        return lista;
    }

    public static long TamanhoDaPasta(string pasta)
    {
        long total = 0;
        try
        {
            foreach (string f in Directory.GetFiles(pasta, "*", SearchOption.AllDirectories))
            {
                try { total += new FileInfo(f).Length; } catch (Exception) { }
            }
        }
        catch (Exception) { }
        return total;
    }

    public static void Desinstalar(string pasta, bool modelos, bool dados, Andamento a)
    {
        Registro.Linha("desinstalando " + pasta + (modelos ? " + modelos" : "") + (dados ? " + dados" : ""));
        a.Relatar(5, "Fechando o Paulus…");
        Fechar(pasta);
        if (modelos)
        {
            List<string> doPaulus = ModelosDoPaulus();
            string ollama = AcharOllama();
            if (doPaulus.Count > 0 && ollama != null)
            {
                Process servidor = null;
                int i = 0;
                foreach (string m in doPaulus)
                {
                    a.Relatar(10 + 40.0 * i++ / doPaulus.Count, "Removendo o modelo " + m + "…");
                    if (!OllamaRm(ollama, m) && servidor == null)
                    {
                        // O "ollama rm" fala com o servidor do Ollama; desligado, e ligado uma vez.
                        try
                        {
                            servidor = Process.Start(new ProcessStartInfo(ollama, "serve") { UseShellExecute = false, CreateNoWindow = true });
                            Thread.Sleep(4000);
                        }
                        catch (Exception) { }
                        OllamaRm(ollama, m);
                    }
                }
                if (servidor != null) { try { servidor.Kill(); } catch (Exception) { } }
            }
            a.Relatar(50, "Removendo os modelos de voz e tradução…");
            Apagar(Path.Combine(Casa, "modelos"));
        }
        if (dados)
        {
            a.Relatar(60, "Apagando os dados do escritório…");
            Apagar(Path.Combine(Casa, "dados"));
        }
        a.Relatar(75, "Removendo o programa…");
        LimparInno(pasta);
        foreach (string nome in new[] { "app", "python", "PAULUS.exe", "Desinstalar.exe", "unins000.exe", "unins000.dat",
                                        "app.antigo", "python.antigo", "PAULUS.exe.antigo", "Desinstalar.exe.antigo" })
            Apagar(Path.Combine(pasta, nome));
        if ((Directory.Exists(Path.Combine(pasta, "app")) || Directory.Exists(Path.Combine(pasta, "python"))) && FecharOllama())
        {
            Apagar(Path.Combine(pasta, "app"));
            Apagar(Path.Combine(pasta, "python"));
        }
        TentarApagarVazia(pasta);
        ReligarOllama();
        // O cloudflared que o PAULUS instalou sai com ele: o tunel e do PAULUS,
        // e um cloudflared rodando sem o PAULUS seria a porta de fora sem dono.
        if (Directory.Exists(PastaCloudflared))
        {
            a.Relatar(85, "Removendo o acesso externo (cloudflared)…");
            FecharCloudflared();
            Apagar(PastaCloudflared);
        }
        a.Relatar(90, "Removendo atalhos e registros…");
        ApagarAtalhoDaPasta(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "PAULUS.lnk"), pasta);
        ApagarAtalhoDaPasta(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "PAULUS.lnk"), pasta);
        TirarMenuDoExplorer(pasta);
        TirarProtocolo(pasta);
        ApagarChaveDaPasta(ChaveDe(pasta), pasta);
        // A entrada antiga, de antes de cada pasta ter a sua: sai se era desta.
        ApagarChaveDaPasta(CHAVE, pasta);
        LimparInno(pasta);
        TentarApagarVazia(Casa);
        Registro.Linha("desinstalado");
        a.Relatar(100, "Pronto.");
    }

    static bool OllamaRm(string ollama, string modelo)
    {
        try
        {
            using (var p = Process.Start(new ProcessStartInfo(ollama, "rm " + modelo) { UseShellExecute = false, CreateNoWindow = true }))
            {
                if (!p.WaitForExit(60000)) { p.Kill(); return false; }
                return p.ExitCode == 0;
            }
        }
        catch (Exception) { return false; }
    }

    // ------------------------------------------------------------ calado

    public static int InstalarCalado()
    {
        var o = new Opcoes();
        Instalado ja = LerInstalado();
        o.Pasta = Programa.Valor("/pasta") ?? (ja != null ? ja.Pasta : PastaPadrao);
        bool atualizando = ParecePaulus(o.Pasta);
        if (atualizando)
        {
            // A atualizacao sozinha (ao fechar o PAULUS): mantem o que havia.
            OpcoesDeQuemAtualiza(o);
            if (Programa.Tem("/sem-atalho")) o.AtalhoMesa = false;
            if (Programa.Tem("/sem-iniciar")) o.MenuIniciar = false;
            if (Programa.Tem("/com-explorer")) o.Explorer = true;
        }
        else
        {
            o.AtalhoMesa = !Programa.Tem("/sem-atalho");
            o.MenuIniciar = !Programa.Tem("/sem-iniciar");
            o.Explorer = Programa.Tem("/com-explorer") || MenuDoExplorerLigado(o.Pasta);
            o.Ollama = !Programa.Tem("/sem-ollama");
            // /sem-acesso-de-fora so existe para os testes silenciosos, que
            // nao baixam da internet; a tela nao tem essa escolha.
            o.Tunel = !Programa.Tem("/sem-acesso-de-fora") && !CloudflaredPresente();
        }
        var a = new Andamento();
        string erro = PodeEscrever(o.Pasta);
        if (erro != null) { Registro.Linha(erro); return 2; }
        try { Instalar(o, a); return 0; }
        catch (Exception e) { Registro.Linha("falhou: " + e); return 1; }
    }

    public static int DesinstalarCalado()
    {
        Instalado ja = LerInstalado();
        string pasta = Programa.Valor("/pasta") ?? (ja != null ? ja.Pasta : null);
        if (pasta == null) return 1;
        try { Desinstalar(pasta, Programa.Tem("/apagar-modelos"), Programa.Tem("/apagar-dados"), new Andamento()); ApagarEstaCopiaDepois(); return 0; }
        catch (Exception e) { Registro.Linha("falhou: " + e); return 1; }
    }

    /* A copia temporaria do desinstalador se apaga depois de fechar. */
    public static void ApagarEstaCopiaDepois()
    {
        string eu = Application.ExecutablePath;
        if (!eu.StartsWith(Path.GetTempPath(), StringComparison.OrdinalIgnoreCase)) return;
        try
        {
            Process.Start(new ProcessStartInfo("cmd.exe", "/c ping 127.0.0.1 -n 3 > nul & del /f /q \"" + eu + "\"")
            { UseShellExecute = false, CreateNoWindow = true, WindowStyle = ProcessWindowStyle.Hidden });
        }
        catch (Exception) { }
    }

    // ------------------------------------------------------------- arquivos

    public static void Apagar(string alvo)
    {
        for (int tentativa = 0; tentativa < 5; tentativa++)
        {
            try
            {
                if (Directory.Exists(alvo))
                {
                    foreach (string f in Directory.GetFiles(alvo, "*", SearchOption.AllDirectories))
                        File.SetAttributes(f, FileAttributes.Normal);
                    Directory.Delete(alvo, true);
                }
                else if (File.Exists(alvo)) { File.SetAttributes(alvo, FileAttributes.Normal); File.Delete(alvo); }
                return;
            }
            catch (Exception) { Thread.Sleep(400); }
        }
        Registro.Linha("nao consegui apagar " + alvo);
    }

    static void Mover(string de, string para)
    {
        for (int tentativa = 0; ; tentativa++)
        {
            try
            {
                if (Directory.Exists(de)) Directory.Move(de, para); else File.Move(de, para);
                return;
            }
            catch (IOException e)
            {
                // Dois segundos presa: quase sempre e o Ollama que o PAULUS de
                // antes ligou de dentro da pasta. Fecha (e liga de novo no fim).
                if (tentativa == 4) FecharOllama();
                if (tentativa >= 12)
                    throw new PastaPresaException("A pasta " + de + " está em uso por outro programa. (" + e.Message + ")");
                Thread.Sleep(500);
            }
        }
    }

    static void TentarApagarVazia(string pasta)
    {
        try { if (Directory.Exists(pasta) && Directory.GetFileSystemEntries(pasta).Length == 0) Directory.Delete(pasta); }
        catch (Exception) { }
    }

    static void ApagarTemp(string temp)
    {
        try { Directory.Delete(temp, true); } catch (Exception) { }
    }
}

// ------------------------------------------------------------- tipografia

/* As medidas de uma fonte como o navegador as usa: o avanco de cada letra
   (hmtx), a letra de cada caractere (cmap) e o ajuste entre pares (kerning,
   da tabela GPOS). O GDI+ nao aplica kerning: sem ele as linhas saiam ate 2%
   mais largas que no desenho e quebravam em outro lugar. So o que as fontes do
   instalador usam: PairPos (formatos 1 e 2) do recurso "kern". */
class Metrica
{
    readonly byte[] b;
    public readonly int Upm;
    readonly Dictionary<int, int> glifos = new Dictionary<int, int>();
    readonly int[] avancos;
    readonly List<List<int>> lookups = new List<List<int>>();
    readonly Dictionary<long, int> cache = new Dictionary<long, int>();

    int U16(int o) { return (b[o] << 8) | b[o + 1]; }
    int S16(int o) { return (short)U16(o); }
    int U32(int o) { return (int)(((uint)b[o] << 24) | ((uint)b[o + 1] << 16) | ((uint)b[o + 2] << 8) | b[o + 3]); }

    int Tabela(string tag)
    {
        for (int i = 0, n = U16(4); i < n; i++)
        {
            int r = 12 + 16 * i;
            if (b[r] == tag[0] && b[r + 1] == tag[1] && b[r + 2] == tag[2] && b[r + 3] == tag[3]) return U32(r + 8);
        }
        throw new InvalidDataException("a fonte nao tem a tabela " + tag);
    }

    public Metrica(byte[] ttf)
    {
        b = ttf;
        int head = Tabela("head"), hhea = Tabela("hhea"), hmtx = Tabela("hmtx"), maxp = Tabela("maxp");
        Upm = U16(head + 18);
        int n = U16(maxp + 4), comMedida = U16(hhea + 34), ultimo = 0;
        avancos = new int[n];
        for (int g = 0; g < n; g++) { if (g < comMedida) ultimo = U16(hmtx + 4 * g); avancos[g] = ultimo; }
        LerCmap(Tabela("cmap"));
        try { LerGpos(Tabela("GPOS")); } catch (InvalidDataException) { }
    }

    void LerCmap(int cmap)
    {
        int sub = -1, formato = 0;
        for (int i = 0, n = U16(cmap + 2); i < n; i++)
        {
            int r = cmap + 4 + 8 * i, plat = U16(r), enc = U16(r + 2), o = cmap + U32(r + 4), f = U16(o);
            if (plat == 3 && enc == 10 && f == 12) { sub = o; formato = 12; break; }
            if ((plat == 3 && enc == 1 || plat == 0) && f == 4 && sub < 0) { sub = o; formato = 4; }
        }
        if (formato == 4)
        {
            int seg = U16(sub + 6) / 2, fins = sub + 14, inicios = fins + 2 * seg + 2, deltas = inicios + 2 * seg, faixas = deltas + 2 * seg;
            for (int i = 0; i < seg; i++)
            {
                int fim = U16(fins + 2 * i), ini = U16(inicios + 2 * i), delta = S16(deltas + 2 * i), faixa = U16(faixas + 2 * i);
                if (ini == 0xFFFF) continue;
                for (int c = ini; c <= fim; c++)
                {
                    int g = faixa == 0 ? (c + delta) & 0xFFFF : U16(faixas + 2 * i + faixa + 2 * (c - ini));
                    if (faixa != 0 && g != 0) g = (g + delta) & 0xFFFF;
                    if (g != 0) glifos[c] = g;
                }
            }
        }
        else if (formato == 12)
        {
            for (int i = 0, grupos = U32(sub + 12); i < grupos; i++)
            {
                int r = sub + 16 + 12 * i, ini = U32(r), fim = U32(r + 4), g0 = U32(r + 8);
                for (int c = ini; c <= fim && c - ini < 65536; c++) glifos[c] = g0 + c - ini;
            }
        }
    }

    void LerGpos(int gpos)
    {
        int recursos = gpos + U16(gpos + 6), lista = gpos + U16(gpos + 8);
        var indices = new List<int>();
        for (int i = 0, n = U16(recursos); i < n; i++)
        {
            int r = recursos + 2 + 6 * i;
            if (b[r] != 'k' || b[r + 1] != 'e' || b[r + 2] != 'r' || b[r + 3] != 'n') continue;
            int f = recursos + U16(r + 4);
            for (int j = 0, m = U16(f + 2); j < m; j++) { int li = U16(f + 4 + 2 * j); if (!indices.Contains(li)) indices.Add(li); }
        }
        indices.Sort();
        foreach (int li in indices)
        {
            int lk = lista + U16(lista + 2 + 2 * li), tipo = U16(lk);
            var subs = new List<int>();
            for (int s = 0, n = U16(lk + 4); s < n; s++)
            {
                int st = lk + U16(lk + 6 + 2 * s), t = tipo;
                if (t == 9) { t = U16(st + 2); st += U32(st + 4); }   // extensao
                if (t == 2) subs.Add(st);
            }
            if (subs.Count > 0) lookups.Add(subs);
        }
    }

    int Cobertura(int o, int g)
    {
        int f = U16(o), n = U16(o + 2);
        if (f == 1)
        {
            int lo = 0, hi = n - 1;
            while (lo <= hi) { int m = (lo + hi) / 2, v = U16(o + 4 + 2 * m); if (v == g) return m; if (v < g) lo = m + 1; else hi = m - 1; }
        }
        else if (f == 2)
            for (int i = 0; i < n; i++) { int r = o + 4 + 6 * i; if (g >= U16(r) && g <= U16(r + 2)) return U16(r + 4) + g - U16(r); }
        return -1;
    }

    int Classe(int o, int g)
    {
        int f = U16(o);
        if (f == 1) { int ini = U16(o + 2), n = U16(o + 4); return g >= ini && g < ini + n ? U16(o + 6 + 2 * (g - ini)) : 0; }
        if (f == 2) for (int i = 0, n = U16(o + 2); i < n; i++) { int r = o + 4 + 6 * i; if (g >= U16(r) && g <= U16(r + 2)) return U16(r + 4); }
        return 0;
    }

    static int Bits(int v) { int n = 0; for (v &= 0xFF; v != 0; v &= v - 1) n++; return n; }

    public int Glifo(char c) { int g; return glifos.TryGetValue(c, out g) ? g : 0; }
    public int Avanco(int g) { return g >= 0 && g < avancos.Length ? avancos[g] : 0; }

    /* O ajuste entre g1 e g2, em unidades da fonte: em cada lookup, a primeira sub-tabela que se aplica. */
    public int Kern(int g1, int g2)
    {
        long chave = ((long)g1 << 32) | (uint)g2;
        int v;
        if (cache.TryGetValue(chave, out v)) return v;
        v = 0;
        try
        {
            foreach (List<int> subs in lookups)
            {
                foreach (int st in subs)
                {
                    int formato = U16(st), cob = Cobertura(st + U16(st + 2), g1);
                    if (cob < 0) continue;
                    int vf1 = U16(st + 4), vf2 = U16(st + 6), t1 = 2 * Bits(vf1), t2 = 2 * Bits(vf2), reg = -1;
                    if (formato == 1)
                    {
                        int pares = st + U16(st + 10 + 2 * cob), tam = 2 + t1 + t2, lo = 0, hi = U16(pares) - 1;
                        while (lo <= hi)
                        {
                            int m = (lo + hi) / 2, r = pares + 2 + tam * m, segundo = U16(r);
                            if (segundo == g2) { reg = r + 2; break; }
                            if (segundo < g2) lo = m + 1; else hi = m - 1;
                        }
                        if (reg < 0) continue;
                    }
                    else if (formato == 2)
                    {
                        int c1 = Classe(st + U16(st + 8), g1), c2 = Classe(st + U16(st + 10), g2), n2 = U16(st + 14);
                        if (c1 >= U16(st + 12) || c2 >= n2) break;
                        reg = st + 16 + (c1 * n2 + c2) * (t1 + t2);
                    }
                    else continue;
                    if ((vf1 & 4) != 0) v += S16(reg + 2 * Bits(vf1 & 3));
                    if ((vf2 & 4) != 0) v += S16(reg + t1 + 2 * Bits(vf2 & 3));
                    break;
                }
            }
        }
        catch (Exception) { v = 0; }
        cache[chave] = v;
        return v;
    }
}

/* Uma fonte do desenho: a do GDI+ e as medidas do .ttf (sem elas, quando a
   fonte nao carregou e ficou a do Windows, mede o GDI+). Tamanho, subida e
   descida em pixels da tela. */
class Fonte : IDisposable
{
    public readonly Font F;
    public readonly Metrica M;
    public readonly float Px, Sobe, Desce;

    public Fonte(FontFamily familia, Metrica m, float px)
    {
        F = new Font(familia, px, FontStyle.Regular, GraphicsUnit.Pixel);
        M = m;
        Px = px;
        float em = familia.GetEmHeight(FontStyle.Regular);
        Sobe = px * familia.GetCellAscent(FontStyle.Regular) / em;
        Desce = px * familia.GetCellDescent(FontStyle.Regular) / em;
    }

    public void Dispose() { F.Dispose(); }
}

static class Fontes
{
    // Uma colecao por arquivo, achada pelo nome do arquivo: o Windows de hoje le
    // o nome destas fontes com o peso no fim ("PAULUS Manrope Medio Medium"), e
    // procurar pelo nome da familia caia na Segoe UI.
    static readonly List<PrivateFontCollection> colecoes = new List<PrivateFontCollection>();
    static readonly Dictionary<string, FontFamily> familias = new Dictionary<string, FontFamily>(StringComparer.OrdinalIgnoreCase);
    static readonly Dictionary<string, Metrica> metricas = new Dictionary<string, Metrica>(StringComparer.OrdinalIgnoreCase);
    static string pasta;

    public static void Carregar()
    {
        pasta = Path.Combine(Path.GetTempPath(), "PAULUS-fontes-" + Process.GetCurrentProcess().Id);
        try
        {
            Directory.CreateDirectory(pasta);
            Assembly eu = Assembly.GetExecutingAssembly();
            foreach (string nome in eu.GetManifestResourceNames())
            {
                if (!nome.EndsWith(".ttf", StringComparison.OrdinalIgnoreCase)) continue;
                byte[] dados;
                using (Stream s = eu.GetManifestResourceStream(nome))
                using (var m = new MemoryStream()) { s.CopyTo(m); dados = m.ToArray(); }
                string arq = Path.Combine(pasta, nome), chave = Path.GetFileNameWithoutExtension(nome);
                File.WriteAllBytes(arq, dados);
                var c = new PrivateFontCollection();
                c.AddFontFile(arq);
                colecoes.Add(c);
                if (c.Families.Length > 0) familias[chave] = c.Families[0];
                try { metricas[chave] = new Metrica(dados); }
                catch (Exception e) { Registro.Linha("fonte " + nome + ": " + e.Message); }
            }
        }
        catch (Exception e) { Registro.Linha("fontes: " + e.Message); }
    }

    public static void Liberar()
    {
        try { foreach (PrivateFontCollection c in colecoes) c.Dispose(); Directory.Delete(pasta, true); } catch (Exception) { }
    }

    static Fonte Montar(string arquivo, string reserva, float px)
    {
        FontFamily f;
        Metrica m;
        if (familias.TryGetValue(arquivo, out f)) return new Fonte(f, metricas.TryGetValue(arquivo, out m) ? m : null, px);
        try { f = new FontFamily(reserva); } catch (Exception) { f = FontFamily.GenericSansSerif; }
        return new Fonte(f, null, px);
    }

    /* A serifa (EB Garamond) so em PAVLVS e no titulo de cada tela. */
    public static Fonte Serifa(float px) { return Montar("PAULUSGaramond", "Georgia", px); }

    public static Fonte Texto(float px, int peso)
    {
        return Montar(peso >= 600 ? "PAULUSManropeSeminegrito" : peso >= 500 ? "PAULUSManropeMedio" : "PAULUSManrope", "Segoe UI", px);
    }
}

// -------------------------------------------------------------- as cores

class Tema
{
    // As do desenho (Instalador.dc.html, TEMAS), que sao as do site (site/assets/site.css).
    public Color Bg, Lateral, Tinta, Tinta2, Tinta3, Fio, Preenche, Campo, Barra, PontoFuturo, Trilho, Pastilha, PastilhaEm;
    public bool Claro;

    static Color H(string hex) { return ColorTranslator.FromHtml(hex); }

    public static Tema DoWindows()
    {
        bool claro = true;
        try
        {
            using (RegistryKey k = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"))
                if (k != null && k.GetValue("AppsUseLightTheme") is int) claro = (int)k.GetValue("AppsUseLightTheme") != 0;
        }
        catch (Exception) { }
        return Montar(claro);
    }

    public static Tema Montar(bool claro)
    {
        var t = new Tema();
        t.Claro = claro;
        if (claro)
        {
            t.Bg = H("#f6f5f1"); t.Lateral = H("#f6f5f1"); t.Tinta = H("#1c1c1a"); t.Tinta2 = H("#55544f"); t.Tinta3 = H("#77766f");
            t.Fio = Color.FromArgb(31, 28, 28, 26); t.Preenche = H("#e8e7e1"); t.Campo = H("#efeee9"); t.Barra = H("#1c1c1a");
            t.PontoFuturo = H("#dad9d2"); t.Trilho = H("#efeee9"); t.Pastilha = H("#e2e1db"); t.PastilhaEm = H("#dad9d2");
        }
        else
        {
            t.Bg = H("#131312"); t.Lateral = H("#131312"); t.Tinta = H("#f2f1ec"); t.Tinta2 = H("#a8a69e"); t.Tinta3 = H("#6f6e68");
            t.Fio = Color.FromArgb(26, 242, 241, 236); t.Preenche = H("#20201e"); t.Campo = H("#1a1a18"); t.Barra = H("#f2f1ec");
            t.PontoFuturo = H("#2a2a27"); t.Trilho = H("#1a1a18"); t.Pastilha = H("#2a2a27"); t.PastilhaEm = H("#303030");
        }
        return t;
    }
}

// ----------------------------------------------------------------- a janela

class Alvo
{
    public RectangleF Area;
    public string Id;
    public Action Fazer;
}

enum Tela { BoasVindas, JaInstalado, Local, Instalando, Pronto, Erro, Desinstalar, Desinstalando, Desinstalado }
enum Dialogo { Nenhum, PastaExiste, FecharPaulus, Cancelar }
enum Jeito { Principal, Contorno, Texto }

class Janela : Form
{
    // O desenho (Instalador.dc.html): 720 x 540 a 96 DPI, com 1 px de fio em
    // volta. As medidas sao as dele, em pixels do desenho, e ja contam esse fio;
    // F() e P() passam para os pixels da tela.
    const float LARGURA = 720, ALTURA = 540;
    const float COLUNA = 237, TOPO = 53, LINHA = 448;   // a coluna do conteudo
    const float FIO = 475;                               // o fio do rodape
    const float BOTOES = 507;                            // o meio da fileira de baixo
    const float DIREITA = 687;                           // onde a fileira termina

    readonly bool modoDesinstalar;
    readonly Tema t = Tema.DoWindows();
    readonly float k;
    Tela tela;
    Dialogo dialogo = Dialogo.Nenhum;
    readonly List<Alvo> alvos = new List<Alvo>();
    string sobre = "";
    Action principal, voltar;

    readonly Opcoes o = new Opcoes();
    Instalado instalado;
    bool temOllama = true;
    long tamanhoOllama;
    bool temCloudflared = true;
    long tamanhoCloudflared;
    bool abrirNoFim = true, apagarModelos, apagarDados, modoAtualizar;
    // A remocao comecou (pelo desinstalador ou pela tela "Ja instalado"): o erro diz "desinstalar".
    bool removendo;
    // O que ficou depois de desinstalar: lido uma vez, no fim, e nao a cada pintura.
    bool ficaramDados, ficaramModelos, ficouOllama;
    double progresso;
    string acao = "", erro = "", aviso = "";
    Andamento andamento;
    Thread trabalho;

    public static string MB(long bytes)
    {
        double mb = bytes / 1048576.0;
        return mb >= 1024 ? (mb / 1024).ToString("0.0").Replace('.', ',') + " GB" : mb.ToString("0.0").Replace('.', ',') + " MB";
    }

    public Janela(bool desinstalar)
    {
        modoDesinstalar = desinstalar;
        using (Graphics g = Graphics.FromHwnd(IntPtr.Zero)) k = g.DpiX / 96f;
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(S(LARGURA), S(ALTURA));
        Text = desinstalar ? "Desinstalar o Paulus" : "Instalar o Paulus";
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }
        DoubleBuffered = true;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        KeyPreview = true;

        instalado = Motor.LerInstalado();
        if (desinstalar)
        {
            o.Pasta = Programa.Valor("/pasta") ?? (instalado != null ? instalado.Pasta : Motor.PastaPadrao);
            tela = Tela.Desinstalar;
        }
        else
        {
            temOllama = Motor.OllamaPresente();
            o.Ollama = !temOllama;
            // O cloudflared vem sempre que falta (instalacao e atualizacao),
            // sem caixa de marcar: instalar nao liga o acesso a distancia.
            temCloudflared = Motor.CloudflaredPresente();
            o.Tunel = !temCloudflared;
            if (instalado != null) { o.Pasta = instalado.Pasta; o.Explorer = Motor.MenuDoExplorerLigado(instalado.Pasta); tela = Tela.JaInstalado; }
            else { o.Pasta = Programa.Valor("/pasta") ?? Motor.PastaPadrao; tela = Tela.BoasVindas; }
            // Aberto pelo proprio PAULUS (Configuracoes › Versao): atualiza sem
            // perguntar nada, com o andamento, e abre a versao nova no fim.
            if (Programa.Tem("/atualizar") && (instalado != null || Programa.Valor("/pasta") != null))
            {
                modoAtualizar = true;
                o.Pasta = Programa.Valor("/pasta") ?? instalado.Pasta;
                Motor.OpcoesDeQuemAtualiza(o);
                abrirNoFim = true;
                Shown += delegate { ComecarInstalacao(); };
            }
            if (!temOllama)
                ThreadPool.QueueUserWorkItem(delegate { tamanhoOllama = Motor.TamanhoDoOllama(); try { BeginInvoke((Action)Invalidate); } catch (Exception) { } });
            if (!temCloudflared)
                ThreadPool.QueueUserWorkItem(delegate { tamanhoCloudflared = Motor.TamanhoDoCloudflared(); try { BeginInvoke((Action)Invalidate); } catch (Exception) { } });
        }
    }

    int S(float v) { return (int)Math.Round(v * k); }
    float F(float v) { return v * k; }
    /* O pixel inteiro mais proximo: o navegador poe as caixas assim. */
    float P(float v) { return (float)Math.Floor(v * k + .5f); }
    RectangleF R(float x, float y, float w, float h) { float x0 = P(x), y0 = P(y); return new RectangleF(x0, y0, P(x + w) - x0, P(y + h) - y0); }
    /* A espessura de um fio de 1 px do desenho (o navegador arredonda para baixo). */
    float Fino() { return Math.Max(1f, (float)Math.Floor(k)); }

    protected override CreateParams CreateParams
    {
        get
        {
            CreateParams cp = base.CreateParams;
            cp.Style |= 0x00020000 | 0x00080000;   // WS_MINIMIZEBOX | WS_SYSMENU: a barra de tarefas minimiza e volta
            cp.ClassStyle |= 0x00020000;           // CS_DROPSHADOW
            return cp;
        }
    }

    // ------------------------------------------------------------ desenho

    static GraphicsPath Arredondado(RectangleF r, float raio)
    {
        var p = new GraphicsPath();
        float d = Math.Min(raio * 2, Math.Min(r.Width, r.Height));
        if (d <= 0) { p.AddRectangle(r); return p; }
        p.AddArc(r.X, r.Y, d, d, 180, 90);
        p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        p.CloseFigure();
        return p;
    }

    static void Preencher(Graphics g, Color c, RectangleF r)
    {
        using (var b = new SolidBrush(c)) g.FillRectangle(b, r);
    }

    /* Pinta as formas (juntas, como uma so) pela cobertura de cada pixel da
       area, com Z x Z amostras por pixel. A suavizacao do proprio GDI+ puxa as
       bordas para baixo e para a direita e afina os tracos finos; o navegador
       do desenho nao. Para pecas pequenas: cantos, pontos, icones. Z = 16 nas
       caixas arredondadas e no visto, Z = 4 no X e na seta: o que mais se
       aproximou do desenho, medido pixel a pixel. */
    static void Cobrir(Graphics g, Color cor, Rectangle area, int Z, params GraphicsPath[] formas)
    {
        int w = area.Width, h = area.Height;
        if (w <= 0 || h <= 0) return;
        using (var grande = new Bitmap(w * Z, h * Z, PixelFormat.Format32bppArgb))
        using (var pequeno = new Bitmap(w, h, PixelFormat.Format32bppArgb))
        {
            using (Graphics gg = Graphics.FromImage(grande))
            using (var branco = new SolidBrush(Color.White))
            {
                gg.PixelOffsetMode = PixelOffsetMode.HighQuality;
                gg.ScaleTransform(Z, Z);
                gg.TranslateTransform(-area.X, -area.Y);
                foreach (GraphicsPath f in formas) gg.FillPath(branco, f);
            }
            BitmapData lido = grande.LockBits(new Rectangle(0, 0, w * Z, h * Z), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            var amostras = new byte[lido.Stride * h * Z];
            Marshal.Copy(lido.Scan0, amostras, 0, amostras.Length);
            int passo = lido.Stride;
            grande.UnlockBits(lido);
            BitmapData escrito = pequeno.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            var pixels = new byte[escrito.Stride * h];
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                {
                    int soma = 0;
                    for (int sy = 0; sy < Z; sy++)
                        for (int sx = 0, o = (y * Z + sy) * passo + x * Z * 4 + 3; sx < Z; sx++, o += 4) soma += amostras[o];
                    int i = y * escrito.Stride + x * 4;
                    pixels[i] = cor.B; pixels[i + 1] = cor.G; pixels[i + 2] = cor.R;
                    pixels[i + 3] = (byte)((soma * cor.A + 255 * Z * Z / 2) / (255 * Z * Z));
                }
            Marshal.Copy(pixels, 0, escrito.Scan0, pixels.Length);
            pequeno.UnlockBits(escrito);
            InterpolationMode antes = g.InterpolationMode;
            g.InterpolationMode = InterpolationMode.NearestNeighbor;
            g.DrawImage(pequeno, area, 0, 0, w, h, GraphicsUnit.Pixel);
            g.InterpolationMode = antes;
        }
    }

    /* Uma caixa de cantos arredondados em nove partes: os quatro cantos (q x q)
       com a cobertura exata e o resto reto direto, que cai no pixel inteiro -
       cheia (borda < 0) ou so as faixas da borda. */
    static void PorPartes(Graphics g, Color c, GraphicsPath forma, RectangleF caixa, float raio, int borda)
    {
        Rectangle r = Rectangle.Round(caixa);
        int q = Math.Min((int)Math.Ceiling(raio), Math.Min(r.Width, r.Height) / 2);
        int x0 = r.X, y0 = r.Y, x1 = r.Right, y1 = r.Bottom;
        if (q > 0)
            foreach (Rectangle canto in new[] { new Rectangle(x0, y0, q, q), new Rectangle(x1 - q, y0, q, q),
                                                new Rectangle(x0, y1 - q, q, q), new Rectangle(x1 - q, y1 - q, q, q) })
                Cobrir(g, c, canto, 16, forma);
        using (var b = new SolidBrush(c))
        {
            if (borda < 0)
            {
                g.FillRectangle(b, x0 + q, y0, x1 - x0 - 2 * q, q);
                g.FillRectangle(b, x0, y0 + q, x1 - x0, y1 - y0 - 2 * q);
                g.FillRectangle(b, x0 + q, y1 - q, x1 - x0 - 2 * q, q);
            }
            else
            {
                int v = Math.Max(q, borda);
                g.FillRectangle(b, x0 + q, y0, x1 - x0 - 2 * q, borda);
                g.FillRectangle(b, x0 + q, y1 - borda, x1 - x0 - 2 * q, borda);
                g.FillRectangle(b, x0, y0 + v, borda, y1 - y0 - 2 * v);
                g.FillRectangle(b, x1 - borda, y0 + v, borda, y1 - y0 - 2 * v);
            }
        }
    }

    static void Preencher(Graphics g, Color c, RectangleF r, float raio)
    {
        using (GraphicsPath p = Arredondado(r, raio)) PorPartes(g, c, p, r, raio, -1);
    }

    /* A borda do CSS: um anel por dentro da caixa, da espessura dada. */
    static void Contorno(Graphics g, Color c, RectangleF r, float raio, float espessura)
    {
        using (GraphicsPath fora = Arredondado(r, raio))
        using (GraphicsPath dentro = Arredondado(RectangleF.Inflate(r, -espessura, -espessura), Math.Max(0, raio - espessura)))
        using (var anel = new GraphicsPath(FillMode.Alternate))
        {
            anel.AddPath(fora, false);
            anel.AddPath(dentro, false);
            PorPartes(g, c, anel, r, raio, (int)espessura);
        }
    }

    /* Um traco pelos pontos (pontas e juntas redondas) como forma cheia, para o Cobrir. */
    static GraphicsPath Traco(float largura, params PointF[] pontos)
    {
        var p = new GraphicsPath();
        p.AddLines(pontos);
        using (var pen = new Pen(Color.Black, largura) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round })
            p.Widen(pen);
        p.FillMode = FillMode.Winding;
        return p;
    }

    /* A caixa inteira (em pixels) que cobre a forma, com uma folga. */
    static Rectangle Area(GraphicsPath p)
    {
        RectangleF r = p.GetBounds();
        int x0 = (int)Math.Floor(r.X) - 1, y0 = (int)Math.Floor(r.Y) - 1;
        return new Rectangle(x0, y0, (int)Math.Ceiling(r.Right) + 1 - x0, (int)Math.Ceiling(r.Bottom) + 1 - y0);
    }

    static readonly StringFormat Tipo = MontarFormato();

    static StringFormat MontarFormato()
    {
        var f = (StringFormat)StringFormat.GenericTypographic.Clone();
        f.FormatFlags |= StringFormatFlags.MeasureTrailingSpaces | StringFormatFlags.NoWrap;
        return f;
    }

    static Graphics medidor;

    /* Onde cada letra comeca (pixels da tela, a partir de 0): o avanco, o
       kerning e o espaco entre letras. A ultima posicao e a largura. */
    static float[] Posicoes(Fonte f, string s, float espaco)
    {
        var x = new float[s.Length + 1];
        if (f.M == null)
        {
            if (medidor == null) medidor = Graphics.FromImage(new Bitmap(1, 1));
            for (int i = 0; i < s.Length; i++) x[i + 1] = x[i] + medidor.MeasureString(s[i].ToString(), f.F, PointF.Empty, Tipo).Width + espaco;
            return x;
        }
        int g = s.Length > 0 ? f.M.Glifo(s[0]) : 0;
        for (int i = 0; i < s.Length; i++)
        {
            int prox = i + 1 < s.Length ? f.M.Glifo(s[i + 1]) : -1;
            x[i + 1] = x[i] + (f.M.Avanco(g) + (prox >= 0 ? f.M.Kern(g, prox) : 0)) * f.Px / f.M.Upm + espaco;
            g = prox;
        }
        return x;
    }

    /* A largura de um texto, em pixels da tela. */
    static float Largura(Fonte f, string s, float espaco) { return Posicoes(f, s, espaco)[s.Length]; }
    static float Largura(Fonte f, string s) { return Largura(f, s, 0); }

    /* Escreve letra a letra, cada uma no pixel inteiro mais proximo, como o
       navegador. x em pixels do desenho; a base em pixels da tela. O GDI+ poe a
       base no pixel do topo pedido mais a subida arredondada: com o topo inteiro,
       a base fica onde se quer. */
    void Escrever(Graphics g, string s, Fonte f, Color c, float x, float baseDaLinha, float espaco)
    {
        float[] pos = Posicoes(f, s, espaco);
        float x0 = F(x), y = baseDaLinha - (float)Math.Floor(f.Sobe + .5f);
        using (var b = new SolidBrush(c))
            for (int i = 0; i < s.Length; i++)
            {
                if (char.IsWhiteSpace(s[i])) continue;
                // O par de uma letra fora do plano basico (um emoji num caminho) vai junto.
                int n = char.IsHighSurrogate(s[i]) && i + 1 < s.Length ? 2 : 1;
                g.DrawString(s.Substring(i, n), f.F, b, (float)Math.Floor(x0 + pos[i] + .5f), y, Tipo);
                i += n - 1;
            }
    }

    /* A base de uma linha de texto, com a conta do navegador: a fonte (subida e
       descida arredondadas) centrada na caixa da linha, a sobra arredondada para
       baixo e a base no pixel mais proximo. topo e altura em pixels do desenho;
       a base volta em pixels da tela. */
    float Base(Fonte f, float topo, float altura)
    {
        float sobe = (float)Math.Floor(f.Sobe + .5f), desce = (float)Math.Floor(f.Desce + .5f);
        return (float)Math.Floor(F(topo) + Math.Floor((F(altura) - sobe - desce) / 2) + sobe + .5f);
    }

    /* A base de uma linha centrada em "meio" (a altura normal da fonte, como num botao). */
    float BaseNoMeio(Fonte f, float meio)
    {
        float sobe = (float)Math.Floor(f.Sobe + .5f), desce = (float)Math.Floor(f.Desce + .5f);
        return (float)Math.Floor(F(meio) - (sobe + desce) / 2 + sobe + .5f);
    }

    /* As linhas de um texto na largura (pixels do desenho), como o navegador
       quebra (overflow-wrap: anywhere; com "bonito", text-wrap: pretty): pela
       ordem, cabendo o que couber; uma palavra maior que a linha quebra depois
       de um hifen ou em qualquer letra. Se a ultima linha ficou com uma palavra
       so e curta (menos de um terco da largura), as quebras sao refeitas pelo
       menor custo - a soma do quadrado da sobra de cada linha, com uma multa
       alta para a palavra sozinha no fim -, se der o mesmo numero de linhas
       (o otimizador do Chrome, score_line_breaker.cc). */
    List<string> Quebrar(Fonte f, string texto, float largura, bool bonito)
    {
        var linhas = new List<string>();
        foreach (string paragrafo in texto.Replace("\r", "").Split('\n')) linhas.AddRange(QuebrarParagrafo(f, paragrafo, largura, bonito));
        return linhas;
    }

    List<string> QuebrarParagrafo(Fonte f, string texto, float largura, bool bonito)
    {
        float max = F(largura) + .01f;
        // Os pedacos entre as oportunidades de quebra: o espaco, e depois do hifen que nao vem antes de numero.
        var pedacos = new List<string>();
        var juntas = new List<string>();   // o que vai entre um pedaco e o seguinte quando ficam na mesma linha
        int ini = 0;
        for (int i = 0; i < texto.Length; i++)
        {
            if (texto[i] == ' ') { pedacos.Add(texto.Substring(ini, i - ini)); juntas.Add(" "); ini = i + 1; }
            else if (texto[i] == '-' && i > ini && i + 1 < texto.Length && texto[i + 1] != ' ' && !char.IsDigit(texto[i + 1]))
            { pedacos.Add(texto.Substring(ini, i + 1 - ini)); juntas.Add(""); ini = i + 1; }
        }
        pedacos.Add(texto.Substring(ini));
        juntas.Add("");

        Func<int, int, string> juntar = delegate (int a, int z)
        {
            var sb = new StringBuilder();
            for (int i = a; i < z; i++) { sb.Append(pedacos[i]); if (i + 1 < z) sb.Append(juntas[i]); }
            return sb.ToString();
        };

        // A gulosa.
        var quebras = new List<int>();   // onde comeca cada linha
        int c0 = 0;
        while (c0 < pedacos.Count)
        {
            string p = pedacos[c0];
            if (p.Length > 1 && Largura(f, p) > max)
            {
                int n = p.Length - 1;
                while (n > 1 && Largura(f, p.Substring(0, n)) > max) n--;
                pedacos[c0] = p.Substring(0, n);
                pedacos.Insert(c0 + 1, p.Substring(n));
                juntas.Insert(c0, "");
                quebras.Add(c0);
                c0++;
                continue;
            }
            int z = c0 + 1;
            while (z < pedacos.Count && Largura(f, juntar(c0, z + 1)) <= max) z++;
            quebras.Add(c0);
            c0 = z;
        }
        quebras.Add(pedacos.Count);

        int nLinhas = quebras.Count - 1, m = pedacos.Count;
        if (bonito && nLinhas >= 2 && nLinhas <= 4 && m >= 4 && quebras[nLinhas] - quebras[nLinhas - 1] == 1
            && Largura(f, pedacos[m - 1]) < max / 3)
        {
            float tam = f.Px / k;
            double multaLinha = 4.0 * largura * tam, orfa = 10000, cheia = 1e12;
            var custo = new double[m + 1];
            var antes = new int[m + 1];
            var conta = new int[m + 1];
            for (int z = 1; z <= m; z++)
            {
                double melhor = double.MaxValue;
                for (int a = 0; a < z; a++)
                {
                    double sobra = (max - Largura(f, juntar(a, z))) / k, nota;   // a mesma folga da gulosa
                    if (sobra < 0) nota = cheia;
                    else if (z == m) nota = a == m - 1 ? 4 * orfa : 0;
                    else nota = sobra * sobra;
                    if (custo[a] + nota <= melhor) { melhor = custo[a] + nota; antes[z] = a; }
                }
                custo[z] = melhor + (z == m - 1 ? orfa : 0) + multaLinha;
                conta[z] = conta[antes[z]] + 1;
            }
            if (conta[m] == nLinhas)
            {
                quebras.Clear();
                for (int z = m; z > 0; z = antes[z]) quebras.Insert(0, z);
                quebras.Insert(0, 0);
            }
        }

        var linhas = new List<string>();
        for (int i = 0; i + 1 < quebras.Count; i++) linhas.Add(juntar(quebras[i], quebras[i + 1]));
        return linhas;
    }

    /* Texto que quebra na largura; devolve onde terminou (pixels do desenho). */
    float Paragrafo(Graphics g, string texto, Fonte f, Color c, float x, float y, float largura, float entrelinha, bool bonito)
    {
        foreach (string l in Quebrar(f, texto, largura, bonito))
        {
            Escrever(g, l, f, c, x, Base(f, y, entrelinha), 0);
            y += entrelinha;
        }
        return y;
    }

    Alvo NovoAlvo(RectangleF r, string id, Action fazer)
    {
        var a = new Alvo { Area = r, Id = id, Fazer = fazer };
        alvos.Add(a);
        return a;
    }

    /* O texto com ClearType quando o Windows usa ClearType (como o navegador do desenho). */
    static bool ClearType()
    {
        try { return SystemInformation.IsFontSmoothingEnabled && SystemInformation.FontSmoothingType == 2; }
        catch (Exception) { return false; }
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
        bool ct = ClearType();
        g.TextRenderingHint = ct ? TextRenderingHint.ClearTypeGridFit : TextRenderingHint.AntiAliasGridFit;
        // O contraste que deixa a letra com o mesmo peso da do desenho, em cada tema.
        g.TextContrast = t.Claro ? 2 : (ct ? 8 : 0);
        alvos.Clear();
        principal = null;
        voltar = null;
        g.Clear(t.Bg);

        Lateral(g);
        DesenharBotoesDaJanela(g);
        switch (tela)
        {
            case Tela.BoasVindas: TelaBoasVindas(g); break;
            case Tela.JaInstalado: TelaJaInstalado(g); break;
            case Tela.Local: TelaLocal(g); break;
            case Tela.Instalando: TelaAndamento(g, "PASSO 2 — INSTALAÇÃO", "Instalando…", "Aguarde enquanto o Paulus está sendo instalado."); break;
            case Tela.Pronto: TelaPronto(g); break;
            case Tela.Erro: TelaErro(g); break;
            case Tela.Desinstalar: TelaDesinstalar(g); break;
            case Tela.Desinstalando: TelaAndamento(g, "REMOÇÃO", "Desinstalando…", "Aguarde enquanto o Paulus está sendo removido deste computador."); break;
            case Tela.Desinstalado: TelaDesinstalado(g); break;
        }
        Preencher(g, t.Fio, new RectangleF(P(COLUNA), P(FIO), P(DIREITA) - P(COLUNA), Fino()));

        if (dialogo != Dialogo.Nenhum) DesenharDialogo(g);
        // O fio em volta da janela, por cima de tudo (o escuro do dialogo nao o cobre).
        Contorno(g, t.Fio, new RectangleF(0, 0, ClientSize.Width, ClientSize.Height), 0, Fino());
    }

    bool Remocao()
    {
        return modoDesinstalar || removendo || tela == Tela.Desinstalar || tela == Tela.Desinstalando || tela == Tela.Desinstalado;
    }

    int IndiceDaEtapa(int etapas)
    {
        switch (tela)
        {
            case Tela.BoasVindas: case Tela.JaInstalado: case Tela.Desinstalar: return 0;
            case Tela.Local: case Tela.Desinstalando: return 1;
            case Tela.Instalando: case Tela.Desinstalado: return 2;
            default: return etapas - 1;   // Concluido (e o erro, que termina ali)
        }
    }

    /* A lateral: PAVLVS e as etapas, no mesmo fundo do conteudo, so com o fio na direita. */
    void Lateral(Graphics g)
    {
        Preencher(g, t.Lateral, R(1, 1, 204, ALTURA - 2));
        Preencher(g, t.Fio, new RectangleF(P(204), P(1), Fino(), P(ALTURA - 1) - P(1)));
        using (Fonte marca = Fontes.Serifa(F(20))) Escrever(g, "PAVLVS", marca, t.Tinta, 25, Base(marca, 45, 20), F(2.4f));
        string[] etapas = Remocao() ? new[] { "Desinstalar", "Remoção", "Concluído" } : new[] { "Boas-vindas", "Local", "Instalação", "Concluído" };
        int atual = IndiceDaEtapa(etapas.Length);
        for (int i = 0; i < etapas.Length; i++)
        {
            float y = 103 + 31 * i;
            Color cor = i == atual ? t.Tinta : (i < atual ? t.Tinta2 : t.Tinta3);
            Color ponto = i == atual ? t.Tinta : (i < atual ? t.Tinta2 : t.PontoFuturo);
            Preencher(g, ponto, R(25, y + 7.5f, 6, 6), F(3));
            using (Fonte f = Fontes.Texto(F(13), i == atual ? 600 : 500)) Escrever(g, etapas[i], f, cor, 41, Base(f, y + 1, 18), 0);
        }
    }

    /* Minimizar e fechar, soltos no canto (44 x 32). */
    void DesenharBotoesDaJanela(Graphics g)
    {
        RectangleF minimizar = R(631, 1, 44, 32), fechar = R(675, 1, 44, 32);
        if (sobre == "minimizar") Preencher(g, t.Preenche, minimizar);
        if (sobre == "fechar") Preencher(g, ColorTranslator.FromHtml("#c42b1c"), fechar);
        Preencher(g, sobre == "minimizar" ? t.Tinta : t.Tinta2, new RectangleF(P(648), P(16.5f), P(658) - P(648), Fino()));
        // O X: dois tracos de 14 x 1 girados em volta de (699, 17.5), um por cima do outro.
        foreach (float angulo in new[] { 45f, -45f })
            using (var traco = new GraphicsPath())
            using (var giro = new Matrix())
            {
                traco.AddRectangle(new RectangleF(-F(7), -F(.5f), F(14), F(1)));
                giro.Translate(F(699), F(17.5f));
                giro.Rotate(angulo);
                traco.Transform(giro);
                Cobrir(g, sobre == "fechar" ? Color.White : t.Tinta2, Area(traco), 4, traco);
            }
        NovoAlvo(minimizar, "minimizar", delegate { WindowState = FormWindowState.Minimized; });
        NovoAlvo(fechar, "fechar", PedirParaFechar);
    }

    /* O rotulo em cima do titulo; devolve onde o titulo comeca. */
    float Rotulo(Graphics g, string texto, float y)
    {
        using (Fonte f = Fontes.Texto(F(12), 500)) Escrever(g, texto, f, t.Tinta3, COLUNA, Base(f, y, 16), F(1.68f));
        return y + 16 + 14;
    }

    float Titulo(Graphics g, string texto, float y)
    {
        using (Fonte f = Fontes.Serifa(F(32))) return Paragrafo(g, texto, f, t.Tinta, COLUNA, y, LINHA, 33, true) + 12;
    }

    float Texto(Graphics g, string texto, float y, Color cor)
    {
        using (Fonte f = Fontes.Texto(F(13), 400)) return Paragrafo(g, texto, f, cor, COLUNA, y, LINHA, 19.5f, true) + 12;
    }

    /* A nota miuda (12 px, a cor mais apagada). */
    float Nota(Graphics g, string texto, float y)
    {
        using (Fonte f = Fontes.Texto(F(12), 400)) return Paragrafo(g, texto, f, t.Tinta3, COLUNA, y, LINHA, 16, true);
    }

    /* Uma caixa de marcar com o rotulo ao lado; devolve onde a linha termina. */
    float Caixa(Graphics g, string rotulo, bool marcada, float y, string id, Action fazer)
    {
        RectangleF caixa = R(COLUNA, y + 1.5f, 16, 16);
        if (marcada)
        {
            Preencher(g, t.Tinta, caixa, F(4));
            using (GraphicsPath visto = Traco(F(1.8f), new PointF(caixa.X + F(4), caixa.Y + F(8.2f)), new PointF(caixa.X + F(6.8f), caixa.Y + F(11)),
                                              new PointF(caixa.X + F(12), caixa.Y + F(5.2f))))
                Cobrir(g, t.Bg, Rectangle.Round(caixa), 16, visto);
        }
        else Contorno(g, sobre == id ? t.Tinta2 : t.Tinta3, caixa, F(4), Math.Max(1f, (float)Math.Floor(1.5f * k)));
        float fim;
        using (Fonte f = Fontes.Texto(F(13), 400)) fim = Paragrafo(g, rotulo, f, t.Tinta, COLUNA + 26, y, LINHA - 26, 19.5f, true);
        NovoAlvo(new RectangleF(F(COLUNA), F(y), F(LINHA), F(fim - y)), id, fazer);
        return fim;
    }

    /* Um botao, da direita para a esquerda; devolve a esquerda dele (pixels do desenho).
       - principal: a pastilha (28 px, raio 8) com 1 px de trilho e 1 px de fio em volta, 32 px no total (o padrao de 07/10);
       - contorno: a pastilha com o fio na borda, 28 px;
       - texto: so o rotulo, discreto, na mesma altura. */
    float Botao(Graphics g, string rotulo, float direita, float meio, string id, Action fazer, Jeito jeito, bool noDialogo)
    {
        bool em = sobre == id;
        using (Fonte f = Fontes.Texto(F(12), 500))
        {
            float espaco = noDialogo && jeito == Jeito.Principal ? 0 : .12f;
            // A folga de cada lado do rotulo dentro da pastilha (na fileira de baixo, com 1 px de borda).
            float lado = noDialogo ? 12 : (jeito == Jeito.Texto ? 10 : 12) + 1;
            float pastilha = Largura(f, rotulo, F(espaco)) / k + 2 * lado;
            float largura = pastilha + (jeito == Jeito.Principal ? 4 : noDialogo ? 0 : 2);
            float x = direita - largura;
            float xp = x + (jeito == Jeito.Principal ? 2 : noDialogo ? 0 : 1);
            RectangleF alvo;
            if (jeito == Jeito.Principal)
            {
                alvo = R(x, meio - 16, largura, 32);
                Preencher(g, t.Trilho, alvo, F(10));
                Contorno(g, t.Fio, alvo, F(10), Fino());
                Preencher(g, em ? t.PastilhaEm : t.Pastilha, R(xp, meio - 14, pastilha, 28), F(8));
            }
            else
            {
                alvo = R(xp, meio - 14, pastilha, 28);
                if (jeito == Jeito.Contorno)
                {
                    Preencher(g, em ? t.PastilhaEm : t.Pastilha, alvo, F(8));
                    Contorno(g, t.Fio, alvo, F(8), Fino());
                }
            }
            Escrever(g, rotulo, f, jeito == Jeito.Texto && !em ? t.Tinta2 : t.Tinta, xp + lado, BaseNoMeio(f, meio), F(espaco));
            NovoAlvo(alvo, id, fazer);
            return x;
        }
    }

    /* "Voltar", a esquerda na fileira de baixo. */
    void Voltar(Graphics g, Action aoVoltar)
    {
        Color c = sobre == "voltar" ? t.Tinta : t.Tinta2;
        // A seta do desenho (M1 5h10 M1 5l4-4 M1 5l4 4, traco de 1,2): tres tracos, pintados como um so.
        PointF ponta = new PointF(F(238), F(BOTOES));
        using (GraphicsPath haste = Traco(F(1.2f), ponta, new PointF(F(248), F(BOTOES))))
        using (GraphicsPath cima = Traco(F(1.2f), ponta, new PointF(F(242), F(BOTOES - 4))))
        using (GraphicsPath baixo = Traco(F(1.2f), ponta, new PointF(F(242), F(BOTOES + 4))))
            Cobrir(g, c, Rectangle.Union(Area(haste), Rectangle.Union(Area(cima), Area(baixo))), 4, haste, cima, baixo);
        using (Fonte f = Fontes.Texto(F(12), 500)) Escrever(g, "Voltar", f, c, 254, BaseNoMeio(f, BOTOES), 0);
        NovoAlvo(new RectangleF(F(COLUNA), F(BOTOES - 16), F(50), F(32)), "voltar", aoVoltar);
        voltar = aoVoltar;
    }

    /* A fileira de baixo: Voltar a esquerda (quando ha para onde) e, a direita, Cancelar e o botao principal. */
    void Rodape(Graphics g, Action aoVoltar, bool podeCancelar, string rotulo, Action aoAvancar)
    {
        float dir = DIREITA;
        if (rotulo != null)
        {
            dir = Botao(g, rotulo, dir, BOTOES, "principal", aoAvancar, Jeito.Principal, false) - 8;
            principal = aoAvancar;
        }
        if (podeCancelar) Botao(g, "Cancelar", dir, BOTOES, "cancelar", PedirParaFechar, Jeito.Texto, false);
        if (aoVoltar != null) Voltar(g, aoVoltar);
    }

    void LinhaDeFicha(Graphics g, string chave, string valor, float y)
    {
        using (Fonte f = Fontes.Texto(F(12), 400))
        using (Fonte m = Fontes.Texto(F(12), 500))
        {
            Escrever(g, chave, f, t.Tinta2, COLUNA, Base(f, y, 16), 0);
            Escrever(g, valor, m, t.Tinta, COLUNA + LINHA - Largura(m, valor) / k, Base(m, y, 16), 0);
        }
    }

    /* O caminho da pasta (36 px, raio 12) e, quando da para escolher, o Procurar da mesma altura. */
    float CampoDaPasta(Graphics g, float y, bool comProcurar)
    {
        float wb = 0;
        if (comProcurar)
            using (Fonte fb = Fontes.Texto(F(13), 500))
            {
                wb = Largura(fb, "Procurar…") / k + 30;
                RectangleF rb = R(COLUNA + LINHA - wb, y, wb, 36);
                Preencher(g, t.Pastilha, rb, F(8));
                Contorno(g, sobre == "procurar" ? t.Tinta : t.Fio, rb, F(8), Fino());
                Escrever(g, "Procurar…", fb, t.Tinta, COLUNA + LINHA - wb + 15, BaseNoMeio(fb, y + 18), 0);
                NovoAlvo(rb, "procurar", Procurar);
            }
        float largura = LINHA - (wb > 0 ? wb + 8 : 0);
        RectangleF campo = R(COLUNA, y, largura, 36);
        Preencher(g, t.Campo, campo, F(12));
        Contorno(g, t.Fio, campo, F(12), Fino());
        using (Fonte m = Fontes.Texto(F(12), 400))
        {
            string caminho = o.Pasta;
            while (caminho.Length > 4 && Largura(m, caminho) / k > largura - 26) caminho = "…" + caminho.Substring(2);
            Escrever(g, caminho, m, t.Tinta, COLUNA + 13, BaseNoMeio(m, y + 18), 0);
        }
        return y + 36;
    }

    // --------------------------------------------------------------- telas

    void TelaBoasVindas(Graphics g)
    {
        float y = Rotulo(g, "BEM-VINDO", TOPO);
        y = Titulo(g, "Instalar o Paulus neste computador.", y);
        y = Texto(g, "O Paulus " + Versao.Numero + " será instalado neste computador. Escritório, dados e preferências você define depois, no assistente de configuração.", y, t.Tinta2);
        Texto(g, "Feche os outros aplicativos antes de continuar.", y, t.Tinta2);
        LinhaDeFicha(g, "Versão", Versao.Numero + " · Windows 64 bits", 411);
        LinhaDeFicha(g, "Espaço necessário", MB(Pacote.TamanhoInstalado()), 435);
        Rodape(g, null, true, "Avançar", delegate { tela = Tela.Local; Invalidate(); });
    }

    void TelaJaInstalado(Graphics g)
    {
        float y = Rotulo(g, "JÁ INSTALADO", TOPO);
        y = Titulo(g, "O Paulus já está neste computador.", y);
        string versao = instalado.Versao != "" ? "a versão " + instalado.Versao : "uma versão anterior";
        y = Texto(g, "Está instalada " + versao + ", em " + instalado.Pasta + ". Atualizar troca o programa pela " + Versao.Numero + " e mantém os dados do escritório.", y, t.Tinta2);
        Texto(g, "Desinstalar remove o programa e pergunta se apaga também os dados.", y, t.Tinta2);
        Action atualizar = delegate { tela = Tela.Local; Invalidate(); };
        float dir = Botao(g, "Atualizar", DIREITA, BOTOES, "principal", atualizar, Jeito.Principal, false) - 8;
        principal = atualizar;
        dir = Botao(g, "Desinstalar", dir, BOTOES, "desinstalar", IrParaDesinstalar, Jeito.Contorno, false) - 8;
        Botao(g, "Cancelar", dir, BOTOES, "cancelar", PedirParaFechar, Jeito.Texto, false);
    }

    void IrParaDesinstalar()
    {
        o.Pasta = instalado.Pasta;
        tela = Tela.Desinstalar;
        Invalidate();
    }

    void TelaLocal(Graphics g)
    {
        bool atualizacao = instalado != null && string.Equals(instalado.Pasta, o.Pasta, StringComparison.OrdinalIgnoreCase);
        float y = Rotulo(g, "PASSO 1 — LOCAL", TOPO);
        y = Titulo(g, atualizacao ? "Atualizar aqui." : "Onde instalar?", y);
        y = Texto(g, atualizacao ? "O Paulus instalado nesta pasta será trocado pela versão " + Versao.Numero + ". Os dados do escritório ficam como estão."
                                 : "A pasta abaixo é a recomendada e não exige permissão de administrador.", y, t.Tinta2);
        y = CampoDaPasta(g, y, !atualizacao) + 10;
        // O espaco em disco soma o cloudflared quando ele vem junto.
        long emDisco = Pacote.TamanhoInstalado() + (o.Tunel && !temCloudflared ? Math.Max(tamanhoCloudflared, 60L << 20) : 0);
        using (Fonte f = Fontes.Texto(F(12), 400))
            y = Paragrafo(g, "Pelo menos " + MB(emDisco) + " livres em disco.", f, t.Tinta3, COLUNA, y, LINHA, 18, false) + 20;
        float fim = Caixa(g, "Criar um atalho na área de trabalho", o.AtalhoMesa, y, "mesa", delegate { o.AtalhoMesa = !o.AtalhoMesa; Invalidate(); });
        fim = Caixa(g, "Adicionar ao menu Iniciar", o.MenuIniciar, fim + 11, "iniciar", delegate { o.MenuIniciar = !o.MenuIniciar; Invalidate(); });
        fim = Caixa(g, "“Perguntar ao Paulus” no botão direito do Explorer", o.Explorer, fim + 11, "explorer", delegate { o.Explorer = !o.Explorer; Invalidate(); });
        if (!temOllama)
            fim = Caixa(g, "Instalar componentes opcionais (baixa " + (tamanhoOllama > 0 ? MB(tamanhoOllama) : "mais de 1 GB") + ")",
                        o.Ollama, fim + 11, "ollama", delegate { o.Ollama = !o.Ollama; Invalidate(); });
        // O cloudflared nao e escolha: vem junto, e a tela diz quanto e de onde.
        if (!temCloudflared)
            Nota(g, "Vem junto: o cloudflared, programa da Cloudflare para o acesso à distância (baixa " +
                    (tamanhoCloudflared > 0 ? MB(tamanhoCloudflared) : "uns 55 MB") + " de github.com). Fica desligado até você ligar no Paulus.", fim + 14);
        Rodape(g, delegate { tela = instalado != null ? Tela.JaInstalado : Tela.BoasVindas; Invalidate(); },
               true, atualizacao ? "Atualizar" : "Instalar", PedirParaInstalar);
    }

    void TelaAndamento(Graphics g, string rotulo, string titulo, string texto)
    {
        float y = Rotulo(g, rotulo, TOPO);
        y = Titulo(g, titulo, y);
        y = Texto(g, texto, y, t.Tinta2);
        Preencher(g, t.Preenche, R(COLUNA, y, LINHA, 3));
        float feito = (float)(LINHA * Math.Max(0, Math.Min(100, progresso)) / 100);
        if (feito > 0) Preencher(g, t.Barra, R(COLUNA, y, feito, 3));
        y += 3 + 8;
        using (Fonte m = Fontes.Texto(F(12), 400))
        {
            string pct = Math.Round(progresso) + "%";
            float wp = Largura(m, pct) / k, cabe = LINHA - wp - 16;
            string a = acao;
            if (Largura(m, a) / k > cabe)
            {
                while (a.Length > 1 && Largura(m, a + "…") / k > cabe) a = a.Substring(0, a.Length - 1);
                a = a.TrimEnd() + "…";
            }
            float b = Base(m, y, 16);
            Escrever(g, a, m, t.Tinta2, COLUNA, b, 0);
            Escrever(g, pct, m, t.Tinta2, COLUNA + LINHA - wp, b, 0);
        }
        Rodape(g, null, tela == Tela.Instalando, null, null);
    }

    void TelaPronto(Graphics g)
    {
        float y = Rotulo(g, "CONCLUÍDO", TOPO);
        y = Titulo(g, "O Paulus está instalado.", y);
        y = Texto(g, "Ao abrir, o assistente de configuração fará um teste rápido desta máquina e ajudará a criar ou entrar no seu escritório.", y, t.Tinta2);
        if (aviso != "") y = Texto(g, TextoDoAviso(), y, t.Tinta);
        // O acesso a distancia e um passo do assistente de configuracao, no
        // app: o instalador nao pergunta nada sobre ele.
        Caixa(g, "Abrir o Paulus agora", abrirNoFim, y, "abrir", delegate { abrirNoFim = !abrirNoFim; Invalidate(); });
        Rodape(g, null, false, "Concluir", Concluir);
    }

    /* O aviso do fim. O motor de IA local e o cloudflared sao opcionais: a tela
       inicial do Paulus mostra como completar. Sem a janela do programa
       (WebView2) o Paulus nao abre, e o aviso diz isso. */
    string TextoDoAviso()
    {
        if (aviso.IndexOf("WebView2", StringComparison.Ordinal) >= 0)
            return "A janela do programa (WebView2, da Microsoft) não pôde ser instalada, e o Paulus precisa dela para abrir. Instale o WebView2 pelo site da Microsoft e abra o Paulus de novo.";
        return "Um componente opcional não pôde ser instalado. O Paulus funciona normalmente; a tela inicial mostra como completar a instalação.";
    }

    void TelaErro(Graphics g)
    {
        float y = Rotulo(g, "NÃO DEU CERTO", TOPO);
        y = Titulo(g, Remocao() ? "Não foi possível desinstalar." : "Não foi possível instalar.", y);
        y = Texto(g, Frase(erro), y, t.Tinta2);
        y = Texto(g, "Você pode tentar novamente em instantes. Se o problema persistir, entre em contato com o nosso time de suporte pelo site.", y, t.Tinta2);
        Texto(g, "O registro do que aconteceu está em " + Registro.Arquivo + ".", y, t.Tinta3);
        Rodape(g, null, false, "Fechar", Close);
    }

    /* A mensagem do erro como frase: maiuscula no comeco e ponto no fim. */
    static string Frase(string s)
    {
        s = (s ?? "").Trim();
        if (s == "") return "Aconteceu um erro inesperado.";
        s = char.ToUpper(s[0]) + s.Substring(1);
        return ".!?…".IndexOf(s[s.Length - 1]) >= 0 ? s : s + ".";
    }

    void TelaDesinstalar(Graphics g)
    {
        float y = Rotulo(g, "DESINSTALAR", TOPO);
        y = Titulo(g, "Desinstalar o Paulus?", y);
        y = Texto(g, "Ao prosseguir, você removerá o programa de " + o.Pasta + ". Os documentos das pastas que o Acervo vigia nunca são tocados.", y, t.Tinta2);
        float fim = Caixa(g, "Remover também os componentes baixados pelo Paulus (voz, tradução e modelos).",
                          apagarModelos, y, "modelos", delegate { apagarModelos = !apagarModelos; Invalidate(); });
        fim = Caixa(g, "Apagar também os dados do escritório (conversas, Agenda, Financeiro, cadastros e os documentos da pasta do programa).",
                    apagarDados, fim + 11, "dados", delegate { apagarDados = !apagarDados; Invalidate(); });
        Nota(g, "Se for reinstalar, deixe as duas desmarcadas: os dados e os modelos voltam na próxima instalação.", fim + 14);
        Rodape(g, instalado != null && !Programa.Tem("/relancado") ? (Action)delegate { tela = Tela.JaInstalado; Invalidate(); } : null,
               true, "Desinstalar", PedirParaDesinstalar);
    }

    void TelaDesinstalado(Graphics g)
    {
        float y = Rotulo(g, "CONCLUÍDO", TOPO);
        y = Titulo(g, "O Paulus foi desinstalado.", y);
        string ficou = ficaramDados && ficaramModelos ? "os dados do escritório e os componentes baixados"
                     : ficaramDados ? "os dados do escritório" : ficaramModelos ? "os componentes baixados" : null;
        y = Texto(g, ficou != null ? "Ficaram " + ficou + ", em " + Motor.Casa + ": reinstalar traz tudo de volta."
                                   : "O programa, os dados e os componentes baixados pelo Paulus saíram deste computador.", y, t.Tinta2);
        if (ficouOllama)
            Texto(g, "O Ollama, o motor da IA local, continua instalado. Se não for mais usar, ele sai em Configurações › Aplicativos do Windows.", y, t.Tinta2);
        Rodape(g, null, false, "Concluir", Close);
    }

    // ------------------------------------------------------------- dialogo

    void DesenharDialogo(Graphics g)
    {
        alvos.Clear();
        principal = null;
        voltar = null;
        Preencher(g, Color.FromArgb(115, 0, 0, 0), R(1, 1, LARGURA - 2, ALTURA - 2));
        string titulo, texto, caminho = null, sim, nao;
        Action aoSim;
        if (dialogo == Dialogo.PastaExiste)
        {
            titulo = "A pasta já existe"; texto = "Instalar nela mesmo assim? Os seus dados não são apagados."; caminho = o.Pasta;
            sim = "Sim"; nao = "Não"; aoSim = delegate { dialogo = Dialogo.Nenhum; ConferirAbertoEInstalar(); };
        }
        else if (dialogo == Dialogo.FecharPaulus)
        {
            titulo = "O Paulus está aberto"; texto = "Para continuar, o Paulus precisa fechar. O que não foi salvo nele se perde.";
            sim = "Fechar o Paulus"; nao = "Voltar"; aoSim = delegate { dialogo = Dialogo.Nenhum; Motor.Fechar(o.Pasta); if (tela == Tela.Desinstalar) ComecarDesinstalacao(); else ComecarInstalacao(); };
        }
        else
        {
            titulo = "Cancelar a instalação?";
            texto = andamento != null && andamento.ProgramaPronto
                ? "O Paulus já está instalado; cancelar para só o download que falta."
                : "O que já foi copiado sai, e o que havia antes volta.";
            sim = "Cancelar a instalação"; nao = "Continuar"; aoSim = delegate { dialogo = Dialogo.Nenhum; if (andamento != null) andamento.Cancelar = true; Invalidate(); };
        }
        // A caixa: 440 de largura, raio 16; a barra do titulo (30 px e o fio), e o corpo com 20 px de folga dos lados.
        using (Fonte f = Fontes.Texto(F(13), 400))
        using (Fonte m = Fontes.Texto(F(12), 400))
        using (Fonte ft = Fontes.Texto(F(12), 400))
        {
            List<string> linhas = Quebrar(f, texto, 398, true);
            List<string> linhasC = caminho != null ? Quebrar(m, caminho, 398, false) : new List<string>();
            float h = 1 + 31 + 18 + (caminho != null ? linhasC.Count * 17 + 8 : 0) + linhas.Count * 19.5f + 18 + 32 + 16 + 1;
            float x = 140, y = 1 + (ALTURA - 2 - h) / 2;
            RectangleF caixa = R(x, y, 440, h);
            Preencher(g, t.Campo, caixa, F(16));
            Contorno(g, t.Fio, caixa, F(16), Fino());
            Preencher(g, t.Fio, new RectangleF(P(x + 1), P(y + 31), P(x + 439) - P(x + 1), Fino()));
            Escrever(g, titulo, ft, t.Tinta2, x + 13, BaseNoMeio(ft, y + 16), 0);
            float yy = y + 50;
            foreach (string l in linhasC) { Escrever(g, l, m, t.Tinta2, x + 21, Base(m, yy, 17), 0); yy += 17; }
            if (caminho != null) yy += 8;
            foreach (string l in linhas) { Escrever(g, l, f, t.Tinta, x + 21, Base(f, yy, 19.5f), 0); yy += 19.5f; }
            float meio = yy + 18 + 16;
            float dir = Botao(g, sim, x + 419, meio, "principal", aoSim, Jeito.Principal, true) - 8;
            principal = aoSim;
            Botao(g, nao, dir, meio, "nao", delegate { dialogo = Dialogo.Nenhum; Invalidate(); }, Jeito.Texto, true);
            voltar = delegate { dialogo = Dialogo.Nenhum; Invalidate(); };
        }
    }

    // --------------------------------------------------------------- acoes

    void Procurar()
    {
        string escolhida = SeletorDePasta.Escolher(Handle, Path.GetDirectoryName(o.Pasta));
        if (escolhida == null) return;
        if (!string.Equals(Path.GetFileName(escolhida.TrimEnd('\\')), "PAULUS", StringComparison.OrdinalIgnoreCase))
            escolhida = Path.Combine(escolhida, "PAULUS");
        o.Pasta = escolhida;
        Invalidate();
    }

    void PedirParaInstalar()
    {
        string problema = Motor.PodeEscrever(o.Pasta);
        if (problema != null) { MessageBox.Show(this, problema, "Paulus", MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
        bool atualizacao = instalado != null && string.Equals(instalado.Pasta, o.Pasta, StringComparison.OrdinalIgnoreCase);
        bool temAlgo = Directory.Exists(o.Pasta) && Directory.GetFileSystemEntries(o.Pasta).Length > 0;
        if (temAlgo && !atualizacao) { dialogo = Dialogo.PastaExiste; Invalidate(); return; }
        ConferirAbertoEInstalar();
    }

    void ConferirAbertoEInstalar()
    {
        if (Motor.Abertos(o.Pasta).Count > 0) { dialogo = Dialogo.FecharPaulus; Invalidate(); return; }
        ComecarInstalacao();
    }

    void ComecarInstalacao()
    {
        tela = Tela.Instalando;
        progresso = 0;
        acao = "Preparando…";
        andamento = new Andamento();
        andamento.Relatar = delegate (double p, string a) { try { BeginInvoke((Action)delegate { progresso = p; acao = a; Invalidate(); }); } catch (Exception) { } };
        Invalidate();
        trabalho = new Thread(delegate ()
        {
            try
            {
                Motor.Instalar(o, andamento);
                BeginInvoke((Action)delegate
                {
                    aviso = andamento.Aviso;
                    tela = Tela.Pronto;
                    Invalidate();
                    // No modo atualizar, a versao nova abre sozinha.
                    if (modoAtualizar && aviso == "")
                    {
                        var relogio = new System.Windows.Forms.Timer { Interval = 1500 };
                        relogio.Tick += delegate { relogio.Stop(); Concluir(); };
                        relogio.Start();
                    }
                });
            }
            catch (CanceladoException)
            {
                Registro.Linha("cancelado: o que tinha sido copiado saiu");
                BeginInvoke((Action)Close);
            }
            catch (Exception e)
            {
                Registro.Linha("falhou: " + e);
                BeginInvoke((Action)delegate { erro = e.Message; tela = Tela.Erro; Invalidate(); });
            }
        });
        trabalho.IsBackground = true;
        trabalho.Start();
    }

    void PedirParaDesinstalar()
    {
        if (Motor.Abertos(o.Pasta).Count > 0) { dialogo = Dialogo.FecharPaulus; Invalidate(); return; }
        ComecarDesinstalacao();
    }

    void ComecarDesinstalacao()
    {
        tela = Tela.Desinstalando;
        removendo = true;
        progresso = 0;
        acao = "Preparando…";
        andamento = new Andamento();
        andamento.Relatar = delegate (double p, string a) { try { BeginInvoke((Action)delegate { progresso = p; acao = a; Invalidate(); }); } catch (Exception) { } };
        Invalidate();
        trabalho = new Thread(delegate ()
        {
            try
            {
                Motor.Desinstalar(o.Pasta, apagarModelos, apagarDados, andamento);
                // O que ficou, lido uma vez aqui (e nao a cada pintura da tela).
                bool dados = !apagarDados && Directory.Exists(Path.Combine(Motor.Casa, "dados"));
                bool modelos = !apagarModelos && Directory.Exists(Path.Combine(Motor.Casa, "modelos"));
                bool ollama = Motor.OllamaPresente();
                BeginInvoke((Action)delegate { ficaramDados = dados; ficaramModelos = modelos; ficouOllama = ollama; tela = Tela.Desinstalado; Invalidate(); });
            }
            catch (Exception e)
            {
                Registro.Linha("falhou: " + e);
                BeginInvoke((Action)delegate { erro = e.Message; tela = Tela.Erro; Invalidate(); });
            }
        });
        trabalho.IsBackground = true;
        trabalho.Start();
    }

    void Concluir()
    {
        if (abrirNoFim)
        {
            try
            {
                Process.Start(new ProcessStartInfo(Path.Combine(o.Pasta, "PAULUS.exe"), "")
                { WorkingDirectory = o.Pasta, UseShellExecute = true });
            }
            catch (Exception e) { Registro.Linha("nao abri o PAULUS: " + e.Message); }
        }
        Close();
    }

    void PedirParaFechar()
    {
        if (tela == Tela.Instalando) { dialogo = Dialogo.Cancelar; Invalidate(); return; }
        if (tela == Tela.Desinstalando) return;
        if (tela == Tela.Pronto) { Concluir(); return; }
        Close();
    }

    // -------------------------------------------------------- mouse e teclado

    Alvo Sob(Point p)
    {
        for (int i = alvos.Count - 1; i >= 0; i--) if (alvos[i].Area.Contains(p)) return alvos[i];
        return null;
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        Alvo a = Sob(e.Location);
        string id = a != null ? a.Id : "";
        Cursor = a != null ? Cursors.Hand : Cursors.Default;
        if (id != sobre) { sobre = id; Invalidate(); }
    }

    protected override void OnMouseLeave(EventArgs e)
    {
        if (sobre != "") { sobre = ""; Invalidate(); }
    }

    [DllImport("user32.dll")] static extern bool ReleaseCapture();
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr w, IntPtr l);

    protected override void OnMouseDown(MouseEventArgs e)
    {
        if (e.Button != MouseButtons.Left) return;
        Alvo a = Sob(e.Location);
        if (a != null) { a.Fazer(); return; }
        // Fora de botao, arrasta a janela (nao tem barra de titulo).
        ReleaseCapture();
        SendMessage(Handle, 0xA1, (IntPtr)2, IntPtr.Zero);
    }

    protected override bool ProcessCmdKey(ref Message msg, Keys keyData)
    {
        if (keyData == Keys.Enter && principal != null) { principal(); return true; }
        if (keyData == Keys.Escape)
        {
            if (dialogo != Dialogo.Nenhum) { dialogo = Dialogo.Nenhum; Invalidate(); }
            else PedirParaFechar();
            return true;
        }
        return base.ProcessCmdKey(ref msg, keyData);
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if ((tela == Tela.Instalando || tela == Tela.Desinstalando) && trabalho != null && trabalho.IsAlive && (andamento == null || !andamento.Cancelar))
        {
            e.Cancel = true;
            if (tela == Tela.Instalando) { dialogo = Dialogo.Cancelar; Invalidate(); }
            return;
        }
        base.OnFormClosing(e);
    }
}

// ------------------------------------------------------- escolher a pasta

static class SeletorDePasta
{
    [ComImport, Guid("DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7")]
    class FileOpenDialogRCW { }

    [ComImport, Guid("42f85136-db7e-439c-85f1-e4075d135fc8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IFileDialog
    {
        [PreserveSig] int Show(IntPtr parent);
        void SetFileTypes(uint cFileTypes, IntPtr rgFilterSpec);
        void SetFileTypeIndex(uint iFileType);
        void GetFileTypeIndex(out uint piFileType);
        void Advise(IntPtr pfde, out uint pdwCookie);
        void Unadvise(uint dwCookie);
        void SetOptions(uint fos);
        void GetOptions(out uint pfos);
        void SetDefaultFolder(IShellItem psi);
        void SetFolder(IShellItem psi);
        void GetFolder(out IShellItem ppsi);
        void GetCurrentSelection(out IShellItem ppsi);
        void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string pszName);
        void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string pszName);
        void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string pszTitle);
        void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string pszText);
        void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string pszLabel);
        void GetResult(out IShellItem ppsi);
        void AddPlace(IShellItem psi, int fdap);
        void SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)] string pszDefaultExtension);
        void Close(int hr);
        void SetClientGuid(ref Guid guid);
        void ClearClientData();
        void SetFilter(IntPtr pFilter);
    }

    [ComImport, Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IShellItem
    {
        void BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv);
        void GetParent(out IShellItem ppsi);
        void GetDisplayName(uint sigdnName, [MarshalAs(UnmanagedType.LPWStr)] out string ppszName);
        void GetAttributes(uint sfgaoMask, out uint psfgaoAttribs);
        void Compare(IShellItem psi, uint hint, out int piOrder);
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    static extern void SHCreateItemFromParsingName(string pszPath, IntPtr pbc, ref Guid riid, out IShellItem ppv);

    /* O seletor de pasta do Windows de hoje (o do Explorer); se falhar, o antigo. */
    public static string Escolher(IntPtr dono, string inicial)
    {
        try
        {
            var d = (IFileDialog)new FileOpenDialogRCW();
            d.SetOptions(0x20 | 0x40);   // FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM
            d.SetTitle("Onde instalar o Paulus");
            d.SetOkButtonLabel("Instalar aqui");
            if (inicial != null && Directory.Exists(inicial))
            {
                Guid iid = typeof(IShellItem).GUID;
                IShellItem pasta;
                SHCreateItemFromParsingName(inicial, IntPtr.Zero, ref iid, out pasta);
                d.SetFolder(pasta);
            }
            if (d.Show(dono) != 0) return null;
            IShellItem item;
            d.GetResult(out item);
            string caminho;
            item.GetDisplayName(0x80058000, out caminho);   // SIGDN_FILESYSPATH
            return caminho;
        }
        catch (Exception)
        {
            using (var f = new FolderBrowserDialog())
            {
                f.Description = "Onde instalar o Paulus";
                if (inicial != null && Directory.Exists(inicial)) f.SelectedPath = inicial;
                return f.ShowDialog() == DialogResult.OK ? f.SelectedPath : null;
            }
        }
    }
}

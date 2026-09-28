// O instalador do PAULUS (e o desinstalador: o mesmo programa).
//
// Uma janela so, desenhada aqui, no padrao de docs/ui/instalacao: preto,
// branco e cinza, sem cor de destaque; a lateral com PAVLVS e as etapas. A
// serifa (Garamond) so em PAVLVS e no titulo de cada tela; o resto em Manrope. Quatro telas: Boas-vindas,
// Local, Instalacao, Concluido. Tudo que e escolha (modelo de IA,
// escritorio, dados) fica para o assistente de configuracao, dentro do app.
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
            MessageBox.Show("Este arquivo não traz o programa do PAULUS. Baixe o instalador de novo em paulus.ia.br.",
                "PAULUS", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        Fontes.Carregar();
        Application.Run(new Janela(desinstalar));
        Fontes.Liberar();
        if (desinstalar) Motor.ApagarEstaCopiaDepois();
        return 0;
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
    public bool AtalhoMesa = true, MenuIniciar = true, Explorer = false, Ollama = true;
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
        double fimExtrair = baixarOllama ? 40 : (baixarWebView ? 70 : 85);

        Registro.Linha("instalando em " + pasta + (baixarOllama ? " (com Ollama)" : "") + (baixarWebView ? " (com WebView2)" : ""));
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
            if (guardados.Count == 0) { ApagarChaveDaPasta(CHAVE, pasta); TentarApagarVazia(pasta); }
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
        using (RegistryKey k = Registry.CurrentUser.CreateSubKey(CHAVE))
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
        ta.InvokeMember("Description", BindingFlags.SetProperty, null, a, new object[] { "PAULUS: assistente jurídico de IA local" });
        ta.InvokeMember("Save", BindingFlags.InvokeMethod, null, a, null);
        Marshal.FinalReleaseComObject(a);
        Marshal.FinalReleaseComObject(shell);
    }

    [DllImport("shell32.dll")] static extern void SHChangeNotify(int evento, int flags, IntPtr a, IntPtr b);

    /* "Perguntar ao PAULUS" no botao direito dos arquivos que o programa le.
       No Windows 11 aparece em "Mostrar mais opções". */
    static void MenuDoExplorer(string exe)
    {
        foreach (string tipo in TIPOS)
        {
            using (RegistryKey k = Registry.CurrentUser.CreateSubKey(@"Software\Classes\SystemFileAssociations\" + tipo + @"\shell\PAULUS.Perguntar"))
            {
                k.SetValue("", "Perguntar ao PAULUS");
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
        a.Relatar(5, "Fechando o PAULUS…");
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
        a.Relatar(90, "Removendo atalhos e registros…");
        ApagarAtalhoDaPasta(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "PAULUS.lnk"), pasta);
        ApagarAtalhoDaPasta(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "PAULUS.lnk"), pasta);
        TirarMenuDoExplorer(pasta);
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
        o.AtalhoMesa = !Programa.Tem("/sem-atalho");
        o.MenuIniciar = !Programa.Tem("/sem-iniciar");
        o.Explorer = Programa.Tem("/com-explorer") || MenuDoExplorerLigado(o.Pasta);
        o.Ollama = !Programa.Tem("/sem-ollama");
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

// ------------------------------------------------------------------ fontes

static class Fontes
{
    static PrivateFontCollection colecao = new PrivateFontCollection();
    static string pasta;
    static readonly Dictionary<string, FontFamily> familias = new Dictionary<string, FontFamily>();

    public static void Carregar()
    {
        pasta = Path.Combine(Path.GetTempPath(), "PAULUS-fontes-" + Process.GetCurrentProcess().Id);
        try
        {
            Directory.CreateDirectory(pasta);
            Assembly eu = Assembly.GetExecutingAssembly();
            foreach (string nome in eu.GetManifestResourceNames())
            {
                if (!nome.EndsWith(".ttf")) continue;
                string arq = Path.Combine(pasta, nome);
                using (Stream s = eu.GetManifestResourceStream(nome))
                using (var f = new FileStream(arq, FileMode.Create)) s.CopyTo(f);
                colecao.AddFontFile(arq);
            }
            foreach (FontFamily f in colecao.Families) familias[f.Name] = f;
        }
        catch (Exception e) { Registro.Linha("fontes: " + e.Message); }
    }

    public static void Liberar()
    {
        try { colecao.Dispose(); Directory.Delete(pasta, true); } catch (Exception) { }
    }

    static FontFamily Familia(string nome, string reserva)
    {
        FontFamily f;
        if (familias.TryGetValue(nome, out f)) return f;
        try { return new FontFamily(reserva); } catch (Exception) { return FontFamily.GenericSansSerif; }
    }

    public static Font Serifa(float px, bool medio) { return new Font(Familia(medio ? "PAULUS Garamond Medio" : "PAULUS Garamond", "Georgia"), px, FontStyle.Regular, GraphicsUnit.Pixel); }
    public static Font Texto(float px, int peso)
    {
        string nome = peso >= 600 ? "PAULUS Manrope Seminegrito" : peso >= 500 ? "PAULUS Manrope Medio" : "PAULUS Manrope";
        return new Font(Familia(nome, "Segoe UI"), px, FontStyle.Regular, GraphicsUnit.Pixel);
    }
}

// -------------------------------------------------------------- as cores

class Tema
{
    public Color Bg, Lateral, Tinta, Tinta2, Tinta3, Fio, Preenche, Campo, Botao, BotaoTexto, Botao2, Barra;

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
        var t = new Tema();
        if (claro)
        {
            t.Bg = H("#ffffff"); t.Lateral = H("#f3f3f3"); t.Tinta = H("#161616"); t.Tinta2 = H("#5c5c5c"); t.Tinta3 = H("#8c8c8c");
            t.Fio = Color.FromArgb(26, 0, 0, 0); t.Preenche = H("#ededed"); t.Campo = H("#ffffff");
            t.Botao = H("#161616"); t.BotaoTexto = H("#ffffff"); t.Botao2 = H("#ffffff"); t.Barra = H("#161616");
        }
        else
        {
            t.Bg = H("#141414"); t.Lateral = H("#1c1c1c"); t.Tinta = H("#f2f2f2"); t.Tinta2 = H("#a3a3a3"); t.Tinta3 = H("#737373");
            t.Fio = Color.FromArgb(26, 255, 255, 255); t.Preenche = H("#262626"); t.Campo = H("#1c1c1c");
            t.Botao = H("#f2f2f2"); t.BotaoTexto = H("#141414"); t.Botao2 = H("#262626"); t.Barra = H("#f2f2f2");
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

class Janela : Form
{
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
    bool abrirNoFim = true, apagarModelos, apagarDados;
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
        ClientSize = new Size(S(640), S(480));
        Text = desinstalar ? "Desinstalar o PAULUS" : "Instalar o PAULUS";
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
            if (instalado != null) { o.Pasta = instalado.Pasta; o.Explorer = Motor.MenuDoExplorerLigado(instalado.Pasta); tela = Tela.JaInstalado; }
            else { o.Pasta = Programa.Valor("/pasta") ?? Motor.PastaPadrao; tela = Tela.BoasVindas; }
            if (!temOllama)
                ThreadPool.QueueUserWorkItem(delegate { tamanhoOllama = Motor.TamanhoDoOllama(); try { BeginInvoke((Action)Invalidate); } catch (Exception) { } });
        }
    }

    int S(float v) { return (int)Math.Round(v * k); }
    float F(float v) { return v * k; }

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
        float d = raio * 2;
        if (d <= 0) { p.AddRectangle(r); return p; }
        p.AddArc(r.X, r.Y, d, d, 180, 90);
        p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        p.CloseFigure();
        return p;
    }

    static readonly StringFormat Tipo = MontarFormato();

    static StringFormat MontarFormato()
    {
        var f = (StringFormat)StringFormat.GenericTypographic.Clone();
        f.FormatFlags |= StringFormatFlags.MeasureTrailingSpaces | StringFormatFlags.NoWrap;
        return f;
    }

    static float Largura(Graphics g, string s, Font f) { return g.MeasureString(s, f, PointF.Empty, Tipo).Width; }

    static List<string> Quebrar(Graphics g, string texto, Font f, float largura)
    {
        var linhas = new List<string>();
        foreach (string paragrafo in texto.Split('\n'))
        {
            string linha = "";
            foreach (string inteira in paragrafo.Split(' '))
            {
                string tentativa = linha == "" ? inteira : linha + " " + inteira;
                if (Largura(g, tentativa, f) <= largura) { linha = tentativa; continue; }
                if (linha != "") { linhas.Add(linha); linha = ""; }
                // Palavra maior que a linha (um caminho sem espaco): quebra por letra.
                string palavra = inteira;
                while (palavra.Length > 1 && Largura(g, palavra, f) > largura)
                {
                    int n = palavra.Length - 1;
                    while (n > 1 && Largura(g, palavra.Substring(0, n), f) > largura) n--;
                    linhas.Add(palavra.Substring(0, n));
                    palavra = palavra.Substring(n);
                }
                linha = palavra;
            }
            linhas.Add(linha);
        }
        return linhas;
    }

    /* Caminho nao tem espaco: quebra em qualquer letra. */
    static List<string> QuebrarCaminho(Graphics g, string caminho, Font f, float largura)
    {
        var linhas = new List<string>();
        string linha = "";
        foreach (char c in caminho)
        {
            if (linha != "" && Largura(g, linha + c, f) > largura) { linhas.Add(linha); linha = ""; }
            linha += c;
        }
        if (linha != "") linhas.Add(linha);
        return linhas;
    }

    /* Texto que quebra na largura; devolve onde terminou. */
    float Paragrafo(Graphics g, string texto, Font f, Color c, float x, float y, float largura, float entrelinha)
    {
        using (var b = new SolidBrush(c))
        {
            foreach (string l in Quebrar(g, texto, f, largura))
            {
                g.DrawString(l, f, b, x, y, Tipo);
                y += entrelinha;
            }
        }
        return y;
    }

    /* Letra a letra, com espaco entre elas (PAVLVS e os rotulos em mono). */
    float Espacado(Graphics g, string texto, Font f, Color c, float x, float y, float espaco)
    {
        using (var b = new SolidBrush(c))
        {
            foreach (char ch in texto)
            {
                string s = ch.ToString();
                g.DrawString(s, f, b, x, y, Tipo);
                x += Largura(g, s, f) + espaco;
            }
        }
        return x;
    }

    static Color Misturar(Color a, Color b, float quanto)
    {
        return Color.FromArgb((int)(a.R + (b.R - a.R) * quanto), (int)(a.G + (b.G - a.G) * quanto), (int)(a.B + (b.B - a.B) * quanto));
    }

    Alvo NovoAlvo(RectangleF r, string id, Action fazer)
    {
        var a = new Alvo { Area = r, Id = id, Fazer = fazer };
        alvos.Add(a);
        return a;
    }

    /* Botao cheio (o primario) ou contornado; devolve a esquerda dele. */
    float Botao(Graphics g, string rotulo, float direita, float y, string id, Action fazer, bool cheio, bool contorno)
    {
        using (Font f = Fontes.Texto(F(12.5f), 600))
        {
            float w = Largura(g, rotulo, f) + F(cheio || contorno ? 32 : 28), h = F(32);
            var r = new RectangleF(direita - w, y, w, h);
            bool em = sobre == id;
            Color fundo = cheio ? (em ? Misturar(t.Botao, t.Bg, .12f) : t.Botao) : (contorno ? t.Botao2 : t.Bg);
            Color tinta = cheio ? t.BotaoTexto : (contorno ? t.Tinta : (em ? t.Tinta : t.Tinta2));
            if (cheio || contorno)
                using (GraphicsPath p = Arredondado(r, F(6)))
                {
                    using (var b = new SolidBrush(fundo)) g.FillPath(b, p);
                    if (contorno) using (var pen = new Pen(em ? t.Tinta : t.Fio, 1)) g.DrawPath(pen, p);
                }
            using (var b = new SolidBrush(tinta))
                g.DrawString(rotulo, f, b, r.X + (w - Largura(g, rotulo, f)) / 2, y + (h - f.GetHeight(g)) / 2, Tipo);
            NovoAlvo(r, id, fazer);
            return r.X;
        }
    }

    float Caixa(Graphics g, string rotulo, bool marcada, float x, float y, float largura, string id, Action fazer)
    {
        float lado = F(16);
        var caixa = new RectangleF(x, y + F(1.5f), lado, lado);
        using (GraphicsPath p = Arredondado(caixa, F(4)))
        {
            if (marcada)
            {
                using (var b = new SolidBrush(t.Tinta)) g.FillPath(b, p);
                using (var pen = new Pen(t.Bg, F(1.8f)) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round })
                    g.DrawLines(pen, new[] { new PointF(caixa.X + F(4), caixa.Y + F(8.2f)), new PointF(caixa.X + F(6.8f), caixa.Y + F(11)), new PointF(caixa.X + F(12), caixa.Y + F(5.2f)) });
            }
            else using (var pen = new Pen(sobre == id ? t.Tinta2 : t.Tinta3, F(1.5f))) g.DrawPath(pen, p);
        }
        float fim;
        using (Font f = Fontes.Texto(F(13), 400))
            fim = Paragrafo(g, rotulo, f, t.Tinta, x + lado + F(10), y, largura - lado - F(10), F(19.5f));
        NovoAlvo(new RectangleF(x, y, largura, fim - y), id, fazer);
        return fim;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
        alvos.Clear();
        principal = null;
        voltar = null;
        float W = ClientSize.Width, H = ClientSize.Height;
        g.Clear(t.Bg);

        // A lateral: PAVLVS e as etapas.
        float lat = F(188);
        using (var b = new SolidBrush(t.Lateral)) g.FillRectangle(b, 0, 0, lat, H);
        using (var p = new Pen(t.Fio, 1)) g.DrawLine(p, lat - .5f, 0, lat - .5f, H);
        using (Font marca = Fontes.Serifa(F(26), true)) Espacado(g, "PAVLVS", marca, t.Tinta, F(20), F(38), F(26 * .14f));
        bool remocao = modoDesinstalar || tela == Tela.Desinstalar || tela == Tela.Desinstalando || tela == Tela.Desinstalado;
        string[] etapas = remocao ? new[] { "Desinstalar", "Remoção", "Concluído" } : new[] { "Boas-vindas", "Local", "Instalação", "Concluído" };
        int atual = IndiceDaEtapa();
        float ye = F(40 + 26 + 28);
        for (int i = 0; i < etapas.Length; i++)
        {
            Color cor = i == atual ? t.Tinta : (i < atual ? t.Tinta2 : t.Tinta3);
            Color ponto = i == atual ? t.Tinta : (i < atual ? t.Tinta2 : Misturar(t.Lateral, t.Tinta, .12f));
            using (var b = new SolidBrush(ponto)) g.FillEllipse(b, F(20), ye + F(7.5f), F(6), F(6));
            using (Font f = Fontes.Texto(F(13.5f), i == atual ? 600 : 500))
            using (var b = new SolidBrush(cor)) g.DrawString(etapas[i], f, b, F(36), ye + F(1), Tipo);
            ye += F(31);
        }

        // Minimizar e fechar, soltos no canto.
        DesenharBotoesDaJanela(g, W);

        // O conteudo.
        float x = lat + F(28), largura = W - x - F(28), y = F(44);
        float rodape = H - F(62);
        switch (tela)
        {
            case Tela.BoasVindas: TelaBoasVindas(g, x, y, largura, rodape); break;
            case Tela.JaInstalado: TelaJaInstalado(g, x, y, largura, rodape); break;
            case Tela.Local: TelaLocal(g, x, y, largura, rodape); break;
            case Tela.Instalando: TelaAndamento(g, x, y, largura, rodape, "PASSO 2 — INSTALAÇÃO", "Instalando…", "Aguarde enquanto o PAULUS é instalado."); break;
            case Tela.Pronto: TelaPronto(g, x, y, largura, rodape); break;
            case Tela.Erro: TelaErro(g, x, y, largura, rodape); break;
            case Tela.Desinstalar: TelaDesinstalar(g, x, y, largura, rodape); break;
            case Tela.Desinstalando: TelaAndamento(g, x, y, largura, rodape, "REMOÇÃO", "Desinstalando…", "Aguarde enquanto o PAULUS é removido deste computador."); break;
            case Tela.Desinstalado: TelaDesinstalado(g, x, y, largura, rodape); break;
        }
        using (var p = new Pen(t.Fio, 1)) g.DrawLine(p, x, rodape, W - F(28), rodape);

        if (dialogo != Dialogo.Nenhum) DesenharDialogo(g, W, H);
        using (var p = new Pen(t.Fio, 1)) g.DrawRectangle(p, 0, 0, W - 1, H - 1);
    }

    int IndiceDaEtapa()
    {
        switch (tela)
        {
            case Tela.BoasVindas: case Tela.JaInstalado: case Tela.Desinstalar: return 0;
            case Tela.Local: case Tela.Desinstalando: return 1;
            case Tela.Instalando: return 2;
            case Tela.Desinstalado: return 2;
            default: return 3;
        }
    }

    void DesenharBotoesDaJanela(Graphics g, float W)
    {
        var fechar = new RectangleF(W - F(44), 0, F(44), F(32));
        var minimizar = new RectangleF(W - F(88), 0, F(44), F(32));
        if (sobre == "minimizar") using (var b = new SolidBrush(t.Preenche)) g.FillRectangle(b, minimizar);
        if (sobre == "fechar") using (var b = new SolidBrush(ColorTranslator.FromHtml("#c42b1c"))) g.FillRectangle(b, fechar);
        using (var p = new Pen(sobre == "minimizar" ? t.Tinta : t.Tinta2, 1))
            g.DrawLine(p, minimizar.X + F(17), minimizar.Y + F(16), minimizar.X + F(27), minimizar.Y + F(16));
        using (var p = new Pen(sobre == "fechar" ? Color.White : t.Tinta2, 1))
        {
            float cx = fechar.X + F(22), cy = fechar.Y + F(16), r = F(5);
            g.DrawLine(p, cx - r, cy - r, cx + r, cy + r);
            g.DrawLine(p, cx - r, cy + r, cx + r, cy - r);
        }
        NovoAlvo(minimizar, "minimizar", delegate { WindowState = FormWindowState.Minimized; });
        NovoAlvo(fechar, "fechar", PedirParaFechar);
    }

    float Rotulo(Graphics g, string texto, float x, float y)
    {
        using (Font f = Fontes.Texto(F(10.5f), 500)) Espacado(g, texto, f, t.Tinta3, x, y, F(10.5f * .16f));
        return y + F(16) + F(14);
    }

    float Titulo(Graphics g, string texto, float x, float y, float largura)
    {
        using (Font f = Fontes.Serifa(F(30), false)) return Paragrafo(g, texto, f, t.Tinta, x, y, largura, F(33)) + F(12);
    }

    float Texto(Graphics g, string texto, float x, float y, float largura, Color cor)
    {
        using (Font f = Fontes.Texto(F(13), 400)) return Paragrafo(g, texto, f, cor, x, y, largura, F(19.5f)) + F(12);
    }

    void Rodape(Graphics g, float x, float rodape, bool podeVoltar, Action aoVoltar, bool podeCancelar, string rotulo, Action aoAvancar)
    {
        float W = ClientSize.Width, y = rodape + F(15);
        float dir = W - F(28);
        if (rotulo != null) { dir = Botao(g, rotulo, dir, y, "principal", aoAvancar, true, false) - F(8); principal = aoAvancar; }
        if (podeCancelar) dir = Botao(g, "Cancelar", dir, y, "cancelar", PedirParaFechar, false, false) - F(8);
        if (podeVoltar)
        {
            using (Font f = Fontes.Texto(F(12.5f), 500))
            {
                Color c = sobre == "voltar" ? t.Tinta : t.Tinta2;
                float ay = y + F(16);
                using (var p = new Pen(c, F(1.2f)) { StartCap = LineCap.Round, EndCap = LineCap.Round })
                {
                    g.DrawLine(p, x, ay, x + F(10), ay);
                    g.DrawLine(p, x, ay, x + F(4), ay - F(4));
                    g.DrawLine(p, x, ay, x + F(4), ay + F(4));
                }
                using (var b = new SolidBrush(c)) g.DrawString("Voltar", f, b, x + F(15), y + F(16) - f.GetHeight(g) / 2 - F(1), Tipo);
                NovoAlvo(new RectangleF(x - F(4), y, F(70), F(32)), "voltar", aoVoltar);
                voltar = aoVoltar;
            }
        }
    }

    float LinhaDeFicha(Graphics g, string chave, string valor, float x, float y, float largura)
    {
        using (Font f = Fontes.Texto(F(12), 400))
        using (Font m = Fontes.Texto(F(12), 500))
        {
            using (var b = new SolidBrush(t.Tinta2)) g.DrawString(chave, f, b, x, y, Tipo);
            using (var b = new SolidBrush(t.Tinta)) g.DrawString(valor, m, b, x + largura - Largura(g, valor, m), y, Tipo);
        }
        return y + F(24);
    }

    // --------------------------------------------------------------- telas

    void TelaBoasVindas(Graphics g, float x, float y, float largura, float rodape)
    {
        y = Rotulo(g, "BEM-VINDO", x, y);
        y = Titulo(g, "Instalar o PAULUS neste computador.", x, y, largura);
        y = Texto(g, "Isto instala o PAULUS " + Versao.Numero + " e o motor de IA local. A escolha do modelo, do escritório e dos seus dados acontece depois, no assistente de configuração.", x, y, largura, t.Tinta2);
        Texto(g, "Feche os outros aplicativos antes de continuar.", x, y, largura, t.Tinta2);
        float yb = rodape - F(16) - F(48);
        yb = LinhaDeFicha(g, "Versão", Versao.Numero + " · Windows 64 bits", x, yb, largura);
        LinhaDeFicha(g, "Espaço necessário", MB(Pacote.TamanhoInstalado()), x, yb, largura);
        Rodape(g, x, rodape, false, null, true, "Avançar", delegate { tela = Tela.Local; Invalidate(); });
    }

    void TelaJaInstalado(Graphics g, float x, float y, float largura, float rodape)
    {
        y = Rotulo(g, "JÁ INSTALADO", x, y);
        y = Titulo(g, "O PAULUS já está neste computador.", x, y, largura);
        string versao = instalado.Versao != "" ? "a versão " + instalado.Versao : "uma versão anterior";
        y = Texto(g, "Está instalada " + versao + ", em " + instalado.Pasta + ". Atualizar troca o programa pela " + Versao.Numero + " e mantém os dados do escritório.", x, y, largura, t.Tinta2);
        Texto(g, "Desinstalar remove o programa e pergunta se apaga também os modelos de IA local e os dados.", x, y, largura, t.Tinta2);
        float W = ClientSize.Width, yb = rodape + F(15);
        float dir = Botao(g, "Atualizar", W - F(28), yb, "principal", delegate { tela = Tela.Local; Invalidate(); }, true, false) - F(8);
        principal = delegate { tela = Tela.Local; Invalidate(); };
        dir = Botao(g, "Desinstalar", dir, yb, "desinstalar", IrParaDesinstalar, false, true) - F(8);
        Botao(g, "Cancelar", dir, yb, "cancelar", PedirParaFechar, false, false);
    }

    void IrParaDesinstalar()
    {
        o.Pasta = instalado.Pasta;
        tela = Tela.Desinstalar;
        Invalidate();
    }

    void TelaLocal(Graphics g, float x, float y, float largura, float rodape)
    {
        bool atualizacao = instalado != null && string.Equals(instalado.Pasta, o.Pasta, StringComparison.OrdinalIgnoreCase);
        y = Rotulo(g, "PASSO 1 — LOCAL", x, y);
        y = Titulo(g, atualizacao ? "Atualizar aqui." : "Onde instalar?", x, y, largura);
        y = Texto(g, atualizacao ? "O PAULUS instalado nesta pasta é trocado pela versão " + Versao.Numero + ". Os dados do escritório ficam como estão."
                                : "A pasta abaixo é a recomendada e não exige permissão de administrador.", x, y, largura, t.Tinta2) - F(4);
        // O caminho e o Procurar.
        using (Font m = Fontes.Texto(F(12.5f), 400))
        using (Font fb = Fontes.Texto(F(12.5f), 600))
        {
            float wb = atualizacao ? 0 : Largura(g, "Procurar…", fb) + F(24);
            var campo = new RectangleF(x, y, largura - (wb > 0 ? wb + F(8) : 0), F(33));
            using (GraphicsPath p = Arredondado(campo, F(6)))
            {
                using (var b = new SolidBrush(t.Campo)) g.FillPath(b, p);
                using (var pen = new Pen(t.Fio, 1)) g.DrawPath(pen, p);
            }
            string caminho = o.Pasta;
            while (caminho.Length > 4 && Largura(g, caminho, m) > campo.Width - F(20)) caminho = "…" + caminho.Substring(2);
            using (var b = new SolidBrush(t.Tinta)) g.DrawString(caminho, m, b, campo.X + F(10), campo.Y + (campo.Height - m.GetHeight(g)) / 2, Tipo);
            if (!atualizacao)
            {
                var rb = new RectangleF(x + largura - wb, y, wb, F(33));
                using (GraphicsPath p = Arredondado(rb, F(6)))
                {
                    using (var b = new SolidBrush(t.Botao2)) g.FillPath(b, p);
                    using (var pen = new Pen(sobre == "procurar" ? t.Tinta : t.Fio, 1)) g.DrawPath(pen, p);
                }
                using (var b = new SolidBrush(t.Tinta)) g.DrawString("Procurar…", fb, b, rb.X + F(12), rb.Y + (rb.Height - fb.GetHeight(g)) / 2, Tipo);
                NovoAlvo(rb, "procurar", Procurar);
            }
        }
        y += F(33) + F(10);
        using (Font f = Fontes.Texto(F(12), 400))
            y = Paragrafo(g, "Pelo menos " + MB(Pacote.TamanhoInstalado()) + " livres em disco.", f, t.Tinta3, x, y, largura, F(18)) + F(14);
        y = Caixa(g, "Criar um atalho na área de trabalho", o.AtalhoMesa, x, y, largura, "mesa", delegate { o.AtalhoMesa = !o.AtalhoMesa; Invalidate(); }) + F(10);
        y = Caixa(g, "Adicionar ao menu Iniciar", o.MenuIniciar, x, y, largura, "iniciar", delegate { o.MenuIniciar = !o.MenuIniciar; Invalidate(); }) + F(10);
        y = Caixa(g, "“Perguntar ao PAULUS” no botão direito do Explorer", o.Explorer, x, y, largura, "explorer", delegate { o.Explorer = !o.Explorer; Invalidate(); }) + F(10);
        if (!temOllama)
            Caixa(g, "Instalar o motor de IA local (Ollama · baixa " + (tamanhoOllama > 0 ? MB(tamanhoOllama) : "mais de 1 GB") + " de ollama.com)",
                  o.Ollama, x, y, largura, "ollama", delegate { o.Ollama = !o.Ollama; Invalidate(); });
        Rodape(g, x, rodape, true, delegate { tela = instalado != null ? Tela.JaInstalado : Tela.BoasVindas; Invalidate(); },
               true, atualizacao ? "Atualizar" : "Instalar", PedirParaInstalar);
    }

    void TelaAndamento(Graphics g, float x, float y, float largura, float rodape, string rotulo, string titulo, string texto)
    {
        y = Rotulo(g, rotulo, x, y);
        y = Titulo(g, titulo, x, y, largura);
        y = Texto(g, texto, x, y, largura, t.Tinta2) + F(8);
        var trilho = new RectangleF(x, y, largura, F(3));
        using (var b = new SolidBrush(t.Preenche)) g.FillRectangle(b, trilho);
        using (var b = new SolidBrush(t.Barra)) g.FillRectangle(b, x, y, (float)(largura * Math.Max(0, Math.Min(100, progresso)) / 100), F(3));
        y += F(3) + F(8);
        using (Font m = Fontes.Texto(F(12), 400))
        {
            string pct = Math.Round(progresso) + "%";
            string a = acao;
            while (a.Length > 4 && Largura(g, a, m) > largura - Largura(g, pct, m) - F(16)) a = a.Substring(0, a.Length - 2) + "…";
            using (var b = new SolidBrush(t.Tinta2))
            {
                g.DrawString(a, m, b, x, y, Tipo);
                g.DrawString(pct, m, b, x + largura - Largura(g, pct, m), y, Tipo);
            }
        }
        Rodape(g, x, rodape, false, null, tela == Tela.Instalando, null, null);
    }

    void TelaPronto(Graphics g, float x, float y, float largura, float rodape)
    {
        y = Rotulo(g, "CONCLUÍDO", x, y);
        y = Titulo(g, "O PAULUS está instalado.", x, y, largura);
        y = Texto(g, "Ao abrir, o assistente de configuração faz um teste rápido desta máquina, recomenda o modelo de IA e ajuda a criar ou entrar no seu escritório.", x, y, largura, t.Tinta2);
        if (aviso != "") y = Texto(g, aviso.Trim() + " A tela inicial do PAULUS mostra como seguir.", x, y, largura, t.Tinta);
        Caixa(g, "Abrir o PAULUS agora", abrirNoFim, x, y + F(2), largura, "abrir", delegate { abrirNoFim = !abrirNoFim; Invalidate(); });
        Rodape(g, x, rodape, false, null, false, "Concluir", Concluir);
    }

    void TelaErro(Graphics g, float x, float y, float largura, float rodape)
    {
        y = Rotulo(g, "NÃO INSTALOU", x, y);
        y = Titulo(g, modoDesinstalar ? "Não deu para desinstalar." : "Não deu para instalar.", x, y, largura);
        y = Texto(g, erro, x, y, largura, t.Tinta2);
        Texto(g, "O registro do que aconteceu está em " + Registro.Arquivo + ".", x, y, largura, t.Tinta3);
        Rodape(g, x, rodape, false, null, false, "Fechar", Close);
    }

    void TelaDesinstalar(Graphics g, float x, float y, float largura, float rodape)
    {
        y = Rotulo(g, "DESINSTALAR", x, y);
        y = Titulo(g, "Desinstalar o PAULUS?", x, y, largura);
        y = Texto(g, "Remove o programa de " + o.Pasta + ". Os documentos das pastas que o Acervo vigia nunca são tocados.", x, y, largura, t.Tinta2);
        List<string> doOllama = Motor.ModelosDoPaulus();
        string modelos = "Tirar também os modelos de IA local: os de voz e tradução do PAULUS" +
            (doOllama.Count > 0 ? " e, no Ollama, os que ele baixou (" + string.Join(", ", doOllama.ToArray()) + ")" : "") +
            ". O Ollama e o que você baixou por fora ficam.";
        y = Caixa(g, modelos, apagarModelos, x, y, largura, "modelos", delegate { apagarModelos = !apagarModelos; Invalidate(); }) + F(10);
        y = Caixa(g, "Apagar também os dados do escritório (conversas, Agenda, Financeiro, cadastros e os documentos da pasta do programa).",
                  apagarDados, x, y, largura, "dados", delegate { apagarDados = !apagarDados; Invalidate(); }) + F(6);
        using (Font f = Fontes.Texto(F(12), 400))
            Paragrafo(g, "Se for reinstalar, deixe as duas desmarcadas: os dados e os modelos voltam na próxima instalação.", f, t.Tinta3, x, y, largura, F(18));
        Rodape(g, x, rodape, instalado != null && !Programa.Tem("/relancado"), delegate { tela = Tela.JaInstalado; Invalidate(); }, true, "Desinstalar", PedirParaDesinstalar);
    }

    void TelaDesinstalado(Graphics g, float x, float y, float largura, float rodape)
    {
        y = Rotulo(g, "CONCLUÍDO", x, y);
        y = Titulo(g, "O PAULUS foi desinstalado.", x, y, largura);
        var ficou = new List<string>();
        if (!apagarDados && Directory.Exists(Path.Combine(Motor.Casa, "dados"))) ficou.Add("os dados do escritório");
        if (!apagarModelos && Directory.Exists(Path.Combine(Motor.Casa, "modelos"))) ficou.Add("os modelos de IA local");
        y = Texto(g, ficou.Count > 0 ? "Ficaram " + string.Join(" e ", ficou.ToArray()) + ", em " + Motor.Casa + ": reinstalar traz tudo de volta."
                                  : "O programa, os dados e os modelos do PAULUS saíram deste computador.", x, y, largura, t.Tinta2);
        if (Motor.OllamaPresente())
            Texto(g, "O Ollama, o motor da IA local, continua instalado. Se não for mais usar, ele sai em Configurações › Aplicativos do Windows.", x, y, largura, t.Tinta2);
        Rodape(g, x, rodape, false, null, false, "Concluir", Close);
    }

    // ------------------------------------------------------------- dialogo

    void DesenharDialogo(Graphics g, float W, float H)
    {
        alvos.Clear();
        principal = null;
        voltar = null;
        using (var b = new SolidBrush(Color.FromArgb(115, 0, 0, 0))) g.FillRectangle(b, 0, 0, W, H);
        string titulo, texto, caminho = null, sim, nao;
        Action aoSim;
        if (dialogo == Dialogo.PastaExiste)
        {
            titulo = "A pasta já existe"; texto = "Instalar nela mesmo assim? Os seus dados não são apagados."; caminho = o.Pasta;
            sim = "Sim"; nao = "Não"; aoSim = delegate { dialogo = Dialogo.Nenhum; ConferirAbertoEInstalar(); };
        }
        else if (dialogo == Dialogo.FecharPaulus)
        {
            titulo = "O PAULUS está aberto"; texto = "Para continuar, o PAULUS precisa fechar. O que não foi salvo nele se perde.";
            sim = "Fechar o PAULUS"; nao = "Voltar"; aoSim = delegate { dialogo = Dialogo.Nenhum; Motor.Fechar(o.Pasta); if (tela == Tela.Desinstalar) ComecarDesinstalacao(); else ComecarInstalacao(); };
        }
        else
        {
            titulo = "Cancelar a instalação?";
            texto = andamento != null && andamento.ProgramaPronto
                ? "O PAULUS já está instalado; cancelar para só o download que falta."
                : "O que já foi copiado sai, e o que havia antes volta.";
            sim = "Cancelar a instalação"; nao = "Continuar"; aoSim = delegate { dialogo = Dialogo.Nenhum; if (andamento != null) andamento.Cancelar = true; Invalidate(); };
        }
        float w = F(420), x = (W - w) / 2;
        using (Font f = Fontes.Texto(F(13), 400))
        using (Font m = Fontes.Texto(F(12), 400))
        {
            List<string> linhas = Quebrar(g, texto, f, w - F(40));
            List<string> linhasC = caminho != null ? QuebrarCaminho(g, caminho, m, w - F(40)) : new List<string>();
            float h = F(30) + F(18) + linhas.Count * F(19.5f) + (caminho != null ? linhasC.Count * F(17) + F(8) : 0) + F(18) + F(32) + F(16);
            float y = (H - h) / 2;
            var caixa = new RectangleF(x, y, w, h);
            using (var b = new SolidBrush(t.Bg)) g.FillRectangle(b, caixa);
            using (var p = new Pen(t.Fio, 1)) { g.DrawRectangle(p, caixa.X, caixa.Y, caixa.Width, caixa.Height); g.DrawLine(p, x, y + F(30), x + w, y + F(30)); }
            using (Font ft = Fontes.Texto(F(12), 400))
            using (var b = new SolidBrush(t.Tinta2)) g.DrawString(titulo, ft, b, x + F(12), y + (F(30) - ft.GetHeight(g)) / 2, Tipo);
            float yy = y + F(30) + F(18);
            if (caminho != null)
            {
                using (var b = new SolidBrush(t.Tinta2)) foreach (string l in linhasC) { g.DrawString(l, m, b, x + F(20), yy, Tipo); yy += F(17); }
                yy += F(8);
            }
            yy = Paragrafo(g, texto, f, t.Tinta, x + F(20), yy, w - F(40), F(19.5f)) + F(18);
            float dir = Botao(g, sim, x + w - F(20), yy, "principal", aoSim, true, false) - F(8);
            principal = aoSim;
            Botao(g, nao, dir, yy, "nao", delegate { dialogo = Dialogo.Nenhum; Invalidate(); }, false, true);
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
        if (problema != null) { MessageBox.Show(this, problema, "PAULUS", MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
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
                BeginInvoke((Action)delegate { aviso = andamento.Aviso; tela = Tela.Pronto; Invalidate(); });
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
                BeginInvoke((Action)delegate { tela = Tela.Desinstalado; Invalidate(); });
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
            try { Process.Start(new ProcessStartInfo(Path.Combine(o.Pasta, "PAULUS.exe")) { WorkingDirectory = o.Pasta, UseShellExecute = true }); }
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
            d.SetTitle("Onde instalar o PAULUS");
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
                f.Description = "Onde instalar o PAULUS";
                if (inicial != null && Directory.Exists(inicial)) f.SelectedPath = inicial;
                return f.ShowDialog() == DialogResult.OK ? f.SelectedPath : null;
            }
        }
    }
}

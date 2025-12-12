import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn, ChildProcessWithoutNullStreams } from 'child_process';

let backendProcess: ChildProcessWithoutNullStreams | undefined;
let currentPanel: vscode.WebviewPanel | undefined;

export function activate(context: vscode.ExtensionContext) {

    // --- 1. 백엔드 프로세스 종료 로직 (필수) ---
    context.subscriptions.push(new vscode.Disposable(() => {
        if (currentPanel) {
            currentPanel.dispose();
        }
        if (backendProcess) {
            backendProcess.kill();
            backendProcess = undefined;
        }
    }));

    // --- 2. "Lumi: 시작" 명령어 등록 ---
    context.subscriptions.push(
        vscode.commands.registerCommand('lumi.start', () => {
            
            // 웹뷰가 이미 열려있으면 그냥 보여주기
            if (currentPanel) {
                currentPanel.reveal(vscode.ViewColumn.One);
                return;
            }
            
            // 백엔드 프로세스가 아직 실행되지 않았을 때만 새로 생성
            if (!backendProcess) {
                
                const exePath = vscode.Uri.joinPath(context.extensionUri, 'bin', 'lumi_backend.exe').fsPath;
                if (!fs.existsSync(exePath)) {
                    vscode.window.showErrorMessage('Lumi backend (lumi_backend.exe) not found. Extension might be corrupt.');
                    return;
                }

                backendProcess = spawn(exePath, [], { windowsHide: true });
                
                let isBackendReady = false;

                // --- 프로세스 이벤트 리스너 ---
                backendProcess.stderr.on('data', (data: Buffer) => {
                    const message = data.toString();
                    console.log(`Lumi Backend: ${message}`); // 모든 로그를 콘솔에 출력

                    // Uvicorn이 준비 완료 로그를 보냈는지 확인
                    if (message.includes("Application startup complete") && !isBackendReady) {
                        isBackendReady = true;
                        // 백엔드가 준비된 후 웹뷰 생성
                        createOrShowWebviewPanel(context);
                    }
                    
                    // INFO 로그는 팝업으로 띄우지 않음
                    if ((message.includes("ERROR") || message.includes("Warning")) && !message.includes("INFO")) {
                        vscode.window.showErrorMessage(`Lumi Backend Error: ${message}`);
                    }
                });

                backendProcess.on('exit', (code, signal) => {
                    console.log(`Lumi backend process exited with code ${code}, signal ${signal}`);
                    backendProcess = undefined;
                    if (currentPanel) {
                        currentPanel.dispose();
                    }
                });

                backendProcess.on('error', (err) => {
                    console.error('Failed to start Lumi backend process.', err);
                    vscode.window.showErrorMessage('Failed to start Lumi backend: ' + err.message);
                    backendProcess = undefined;
                });
            
            } else {
                // 백엔드가 이미 실행 중이면, 웹뷰 패널만 새로 엽니다.
                createOrShowWebviewPanel(context);
            }
        })
    );
}

function createOrShowWebviewPanel(context: vscode.ExtensionContext) {
    const column = vscode.window.activeTextEditor
        ? vscode.window.activeTextEditor.viewColumn
        : undefined;

    // 패널이 이미 존재하면, 해당 패널을 활성화
    if (currentPanel) {
        currentPanel.reveal(column);
        return;
    }

    // 패널이 없다면, 새로 생성
    // [경로 수정됨] React UI 빌드 결과물 경로
    const buildPath = vscode.Uri.joinPath(context.extensionUri, 'webview-ui', 'dist');

    currentPanel = vscode.window.createWebviewPanel(
        'lumiPanel',
        'Lumi Assistant',
        column || vscode.ViewColumn.One,
        {
            enableScripts: true,
            localResourceRoots: [buildPath] // [경로 수정됨]
        }
    );

    // 웹뷰 콘텐츠 설정
    currentPanel.webview.html = getWebviewContent(context, buildPath, currentPanel.webview);

    // 패널 생명주기 관리
    currentPanel.onDidDispose(() => {
        currentPanel = undefined;
        // 중요: 사용자가 패널만 닫았을 때 백엔드를 종료하지 않습니다.
    }, null, context.subscriptions);
}

function getWebviewContent(context: vscode.ExtensionContext, buildPath: vscode.Uri, webview: vscode.Webview): string {
    
    const htmlPath = vscode.Uri.joinPath(buildPath, 'index.html');
    if (!fs.existsSync(htmlPath.fsPath)) {
        return `<html><body><h1>Error</h1><p>Failed to load webview content. File not found: ${htmlPath.fsPath}</p></body></html>`;
    }

    let html = fs.readFileSync(htmlPath.fsPath, 'utf8');
    const baseUri = webview.asWebviewUri(buildPath);

    // [필수] CSP 메타 태그 추가
    const csp = `
        <meta http-equiv="Content-Security-Policy" content="
            default-src 'none';
            style-src ${webview.cspSource} 'unsafe-inline';
            script-src ${webview.cspSource} 'unsafe-inline';
            img-src ${webview.cspSource} data:;
            font-src ${webview.cspSource};
            connect-src http://localhost:8000;
            base-uri ${baseUri}/;
        ">
    `;

    // /assets/ 경로를 웹뷰 URI로 변환
    html = html.replace(
        /(src|href)="\.\/assets\/(.*?)"/g,
        `$1="${baseUri}/assets/$2"`
    );
    
    // <head>에 <base> 태그와 CSP 태그를 삽입
    html = html.replace(
        '<head>',
        `<head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <base href="${baseUri}/">
        ${csp}
        `
    );

    return html;
}


export function deactivate() {
    // 확장이 비활성화될 때, activate에서 등록한 Disposable이
    // 자동으로 backendProcess.kill()을 호출하므로
    // 이 함수는 비워두거나 로깅만 해도 됩니다.
    console.log("Lumi extension deactivated.");
}
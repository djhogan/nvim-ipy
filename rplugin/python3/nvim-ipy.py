import sys
import time
import neovim
from jupyter_core.application import JupyterApp
from jupyter_client.consoleapp import JupyterConsoleApp

@neovim.plugin
class Main:
    def __init__(self, vim):
        self.vim = vim
    
    @neovim.function('IPyStart')
    def launch_instance(self, args):
        self.ipy = ZMQVimIPythonApp.launch_instance()

    @neovim.function('IPyRun')
    def run_cell(self, args):
        line = self.vim.eval('getline(".")')
        self.ipy.run_cell(line)

class ZMQVimIPythonApp(JupyterApp, JupyterConsoleApp):
    name = 'jupyter-vim'
    version = '1.0'

    def initialize(self, argv=None):
        super(ZMQVimIPythonApp, self).initialize(argv)
        JupyterConsoleApp.initialize(self)
        print("Initialize called..")

    def start(self):
        super(ZMQVimIPythonApp, self).start()
        print("Start called..")
        import pdb; pdb.set_trace()

    def run_cell(self, cell):
        # TODO flush stale replies
        msg_id = self.kernel_client.execute(cell)
        self._execution_state = 'busy'

        # function handle stuff while executing
        while self._execution_state != 'idle' and self.kernel_client.is_alive():
            time.sleep(0.1)
            self.handle_iopub()
            # TODO handle input request
        while self.kernel_client.is_alive():
            try:
                self.handle_execute_reply(msg_id)
            except Empty:
                pass
            else:
                break
        # TODO handle input request

    def handle_input_request(self, msg_id, timeout=0.1):
        raise NotImplementedError()
        req = self.kernel_client.stdin_channel.get_msg(timeout=timeout)
        self.handle_iopub(msg_id)
        if msg_id == req['parent_header']['msg_id']:
            # TODO handle SIGINT
            content = req['content']

    def handle_execute_reply(self, msg_id, timeout=0.1):
        msg = self.kernel_client.shell_channel.get_msg(block=False, timeout=timeout)
        if msg['parent_header'].get('msg_id', None) == msg_id:
            self.handle_iopub()  # XXX why is this here?
            content = msg['content']
            status = content['status']
            if status == 'aborted':
                raise RuntimeError('Aborted while waiting for shell channel reply.')
            elif status == 'ok':
                for item in content.get('payload', []):
                    source = item['source']
                    raise NotImplementedError('Execute reply payloads.')
            elif status == 'error':
                raise RuntimeError('Waiting for shell channel reply, received error reply.')
        else:
            raise RuntimeError('Waiting for shell channel reply, but received unrelated message.')

    def handle_iopub(self, msg_id=''):
        while self.kernel_client.iopub_channel.msg_ready():
            sub_msg = self.kernel_client.iopub_channel.get_msg()
            msg_type = sub_msg['header']['msg_type']
            parent = sub_msg['parent_header']

            if True: # check if from here
                if msg_type == 'status':
                    self._execution_state = sub_msg['content']['execution_state']
                elif msg_type == 'stream':
                    sys.stdout.write(sub_msg['content']['text'])
                elif msg_type == 'display_data':
                    sys.stdout.write(sub_msg['content']['data']['text/plain'])
                    # TODO handle other data types.
                elif msg_type == 'data_pub':
                    pass # TODO raw data
                elif msg_type == 'execute_result':
                    sys.stdout.write(sub_msg['content']['data']['text/plain'])
                    # TODO
                elif msg_type == 'execute_input':
                    sys.stdout.write(sub_msg['content']['code'] + '\n')
                elif msg_type == 'clear_output':
                    pass # TODO used for clearing output. Useful for animations.
                elif msg_type == 'error':
                    sys.stdout.write(sub_msg)

    def handle_stdin(self, msg_id=''):
        raise NotImplementedError()

    def handle_control(self, msg_id=''):
        raise NotImplementedError()

    def handle_text_output(text):
        self.vim.command(f'new | call setline(".", "{text}")')

import pos_app

_original_show = pos_app.App.show

def show(self, name):
    if name == 'Tables / Dine-in':
        self.clear()
        self.page_tables__dine_in()
        return
    return _original_show(self, name)

pos_app.App.show = show

if __name__ == '__main__':
    pos_app.main()

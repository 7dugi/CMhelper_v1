import uiautomation as auto
import sys

def dump_kakao_uia():
    print("카카오톡 UI 추출을 시작합니다...")
    try:
        # Search for KakaoTalk by Name
        kakao_win = auto.WindowControl(searchDepth=1, Name="카카오톡")
        
        if not kakao_win.Exists(3, 1):
            print("카카오톡 창을 찾을 수 없습니다. 바탕화면에 카카오톡을 띄워주세요.")
            return

        print(f"카카오톡 창 발견! (Name: '{kakao_win.Name}', ClassName: '{kakao_win.ClassName}')")
        
        with open("kakao_uia_dump.txt", "w", encoding="utf-8") as f:
            original_stdout = sys.stdout
            sys.stdout = f
            
            # Log all controls in the tree (max depth 6 to avoid hanging)
            for control, depth in auto.WalkTree(kakao_win, maxDepth=7):
                indent = " " * (depth * 2)
                print(f"{indent}Name: '{control.Name}', ControlType: {control.ControlType}, ClassName: '{control.ClassName}'")
                
            sys.stdout = original_stdout
            
        print("kakao_uia_dump.txt 파일에 성공적으로 저장되었습니다.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump_kakao_uia()

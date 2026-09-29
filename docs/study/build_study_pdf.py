"""Build the Korean Process Studio study guide from source and rerun reference cases.

Requirements: reportlab, numpy, scipy. Run from any working directory.
Korean fonts default to Windows Malgun Gothic; use --font-dir for other locations.
All figures are vector drawings of computed reference cases or labeled schematics.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim_app.run_reference_cases import CASES
from sim_app.service import simulate_request

NAVY = colors.HexColor('#152D46')
INK = colors.HexColor('#233D52')
TEAL = colors.HexColor('#007F86')
BLUE = colors.HexColor('#2874B8')
ORANGE = colors.HexColor('#B75A31')
MUTED = colors.HexColor('#647889')
PALE = colors.HexColor('#EDF5F5')
LINE = colors.HexColor('#D4E1E7')
WHITE = colors.white
W, H = A4
M = 44
CW = W - 2 * M


def para(text, size=10.2, leading=16.1, color=INK, bold=False):
    # Malgun Gothic lacks several Unicode exponent glyphs. Typeset exponents
    # with ReportLab's actual baseline shift instead of silently losing them.
    supers = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺', '0123456789-+')
    subs = str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789')
    text = re.sub('[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+', lambda m: '<super>' + m[0].translate(supers) + '</super>', text)
    text = re.sub('[₀₁₂₃₄₅₆₇₈₉]+', lambda m: '<sub>' + m[0].translate(subs) + '</sub>', text)
    text = text.replace('v̄', 'v_bar')
    text = text.replace('≈', '<font name="MathSymbols">≈</font>')
    return Paragraph(text, ParagraphStyle(
        'kr', fontName='KRBold' if bold else 'KR', fontSize=size,
        leading=leading, textColor=color, wordWrap='CJK',
        splitLongWords=True, alignment=TA_LEFT, spaceAfter=0,
    ))


class Guide:
    def __init__(self, output):
        self.c = canvas.Canvas(str(output), pagesize=A4, pageCompression=1)
        self.c.setTitle('Process Studio | 반도체 공정과 문제 해결, 14일 + 7일')
        self.c.setAuthor('Process Studio portfolio - AI-assisted study material')
        self.c.setSubject('AMK PSE 중심 ALD/Etch 이론, 축약 모델, 실험과 공정 평가')
        self.n = 0
        self.y = 0
        self.layout = []

    def page(self, chapter, title, deck, tag='CORE'):
        if self.n:
            self.finish()
        self.n += 1
        self.c.bookmarkPage(f'p{self.n}')
        self.c.addOutlineEntry(f'{self.n:02d} {title}', f'p{self.n}', level=0, closed=False)
        self.c.setFillColor(NAVY)
        self.c.rect(0, H - 10, W, 10, fill=1, stroke=0)
        self.c.setFont('KRBold', 8)
        self.c.drawString(M, H - 35, 'PROCESS STUDIO   /   SEMICONDUCTOR FIELD NOTES')
        self.c.setFillColor(TEAL)
        self.c.drawRightString(W - M, H - 35, tag)
        self.y = H - 71
        self.text(chapter, size=9, leading=13, color=TEAL, bold=True, gap=8)
        self.text(title, size=23, leading=30, color=NAVY, bold=True, gap=8)
        self.text(deck, size=10.5, leading=16, color=MUTED, gap=17)

    def finish(self):
        self.layout.append({'page': self.n, 'bottom_y': round(self.y, 1)})
        if self.y < 56:
            raise ValueError(f'Page {self.n} overflow: bottom={self.y:.1f}')
        self.c.setStrokeColor(LINE)
        self.c.line(M, 43, W - M, 43)
        self.c.setFillColor(MUTED)
        self.c.setFont('KR', 7.3)
        self.c.drawString(M, 29, '학습용 축약 모델 · 가상 실험 / 장비 실측 검증 전    |    2026.09.30')
        self.c.setFont('KRBold', 8)
        self.c.drawRightString(W - M, 29, f'{self.n:02d} / 32')
        self.c.showPage()

    def text(self, txt, size=10.2, leading=16.1, color=INK, bold=False, gap=9):
        p = para(txt, size, leading, color, bold)
        _, hh = p.wrap(CW, H)
        p.drawOn(self.c, M, self.y - hh)
        self.y -= hh + gap

    def head(self, txt):
        self.text(txt, size=12.2, leading=18, color=NAVY, bold=True, gap=7)

    def bullets(self, items):
        for item in items:
            self.text('• ' + item, gap=6)
        self.y -= 3

    def box(self, title, txt, warning=False):
        p = para(txt, 10, 15.5)
        _, hh = p.wrap(CW - 24, H)
        total = hh + 44
        self.c.setFillColor(colors.HexColor('#FFF3EB') if warning else PALE)
        self.c.roundRect(M, self.y - total, CW, total, 6, fill=1, stroke=0)
        self.c.setFillColor(ORANGE if warning else TEAL)
        self.c.rect(M, self.y - total + 5, 3, total - 10, fill=1, stroke=0)
        self.c.setFont('KRBold', 10)
        self.c.drawString(M + 12, self.y - 19, title)
        p.drawOn(self.c, M + 12, self.y - total + 11)
        self.y -= total + 12

    def eq(self, lines, note=''):
        content = '<br/>'.join(escape(x) for x in lines)
        p = para(content, 10.4, 18, NAVY)
        _, hh = p.wrap(CW - 26, H)
        self.c.setFillColor(colors.HexColor('#F1F4F8'))
        self.c.roundRect(M, self.y - hh - 22, CW, hh + 22, 5, fill=1, stroke=0)
        p.drawOn(self.c, M + 13, self.y - hh - 11)
        self.y -= hh + 31
        if note:
            self.text(note, size=8.6, leading=13.4, color=MUTED, gap=11)

    def table(self, headers, rows, widths=None, size=9.2):
        widths = widths or [CW / len(headers)] * len(headers)
        data = [[para(x, size, size * 1.48, WHITE, True) for x in headers]]
        data += [[para(str(x), size, size * 1.48) for x in row] for row in rows]
        t = Table(data, colWidths=widths, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F4F7FA'), WHITE]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LINEBELOW', (0, 1), (-1, -1), .35, LINE),
        ]))
        _, hh = t.wrap(CW, H)
        t.drawOn(self.c, M, self.y - hh)
        self.y -= hh + 13

    def source(self, txt):
        self.text('근거 / ' + txt, size=8.1, leading=12.1, color=MUTED, gap=6)

    def chart(self, lines, xlabel, ylabel, caption, height=185, ymax=None):
        """Render a small vector line chart; x/y arrays come from model outputs."""
        x0, y0 = M + 44, self.y - height + 34
        ww, hh = CW - 60, height - 62
        xmax = max(max(x) for _, x, _, _ in lines) or 1
        ym = ymax or max(max(y) for _, _, y, _ in lines) * 1.08 or 1
        c = self.c
        for j in range(5):
            yy = y0 + hh * j / 4
            c.setStrokeColor(LINE)
            c.line(x0, yy, x0 + ww, yy)
            c.setFillColor(MUTED)
            c.setFont('KR', 7)
            c.drawRightString(x0 - 6, yy - 2, f'{ym*j/4:.3g}')
        for j in range(5):
            xx = x0 + ww * j / 4
            c.setFillColor(MUTED)
            c.drawCentredString(xx, y0 - 14, f'{xmax*j/4:.3g}')
        for idx, (name, xs, ys, color) in enumerate(lines):
            c.setStrokeColor(color)
            c.setLineWidth(1.8)
            p = c.beginPath()
            for i, (x, y) in enumerate(zip(xs, ys)):
                xx, yy = x0 + ww * x / xmax, y0 + hh * y / ym
                p.moveTo(xx, yy) if i == 0 else p.lineTo(xx, yy)
            c.drawPath(p)
            c.setFillColor(color)
            c.setFont('KR', 7.5)
            c.drawString(x0 + idx * 145, y0 + hh + 12, name)
        c.setFillColor(MUTED)
        c.setFont('KR', 7.5)
        c.drawString(M, y0 + hh + 25, ylabel)
        c.drawRightString(W - M, y0 - 28, xlabel)
        self.y -= height + 2
        self.text(caption, size=8.4, leading=12.7, color=MUTED, gap=13)

    def save(self):
        self.finish()
        assert self.n == 32, self.n
        self.c.save()


def metric(run, key):
    return next(m['value'] for m in run['result']['metrics'] if m['key'] == key)


def series(run, key):
    return next(s for s in run['result']['series'] if s['key'] == key)


def build(output):
    runs = {name: simulate_request(request) for name, request in CASES}
    # Fixed prose and table values must never survive a model change unnoticed.
    expected = {
        'ald_baseline': {'top_thickness_nm': 5.001207726537979, 'conformality_pct': 99.97604686774535},
        'ald_purge_restriction': {'top_thickness_nm': 13.791416393478828, 'conformality_pct': 36.94760492626422},
        'ald_longer_purge': {'top_thickness_nm': 5.003492433575975, 'conformality_pct': 99.9309247540655, 'cycle_time_s': 13},
        'etch_baseline': {'etch_depth_nm': 28.854803127081812, 'mask_loss_nm': 2.5948303438232836, 'selectivity': 11.126234105553339},
        'etch_rf_mismatch': {'etch_depth_nm': 25.78302486955857, 'mask_loss_nm': 1.483333364883022, 'selectivity': 17.396533359923566, 'absorbed_power_w': 280.8},
        'etch_time_compensation': {'etch_depth_nm': 30.083834597237765, 'mask_loss_nm': 1.7305555923635256, 'selectivity': 17.396533359923566},
        'etch_high_bias': {'etch_depth_nm': 34.886431967159595, 'mask_loss_nm': 4.7632194186125725, 'selectivity': 7.326566963934425},
    }
    for case, values in expected.items():
        for key, value in values.items():
            if not math.isclose(metric(runs[case], key), value, rel_tol=2e-7, abs_tol=2e-7):
                raise ValueError(f'{case}/{key} changed; review prose/tables before rebuilding')
    g = Guide(output)

    # 01
    g.page('FIELD GUIDE 01', '반도체 공정과 문제 해결', 'AMK PSE 중심 · ALD / Etch · ASML TSE / KLA FAE 연결 학습', '14 + 7 DAYS')
    g.text('수식을 이해하고,<br/>조건을 바꾸고,<br/>결과를 판단하는 공부.', size=29, leading=42, color=NAVY, bold=True, gap=24)
    g.box('이번 공부의 완성 기준', '슬라이더를 조작하는 데서 끝나지 않는다. 공정 목표를 먼저 정하고, 관측한 이상을 설명할 가설을 세운 뒤, 한 번의 실험이 어떤 가설을 지지하는지 수치와 한계로 설명한다.')
    g.table(['기초', '심화', '실전'], [['공정 흐름·재료·진공<br/>왜 ALD와 Etch가 필요한가', '수송·표면 반응·플라즈마<br/>수식의 단위와 적용 범위', '규격·계측·DOE·원인 구분<br/>개선 효과와 부작용 평가']], size=10)
    g.text('하루 90-120분, 14일 핵심 과정. 시간이 있으면 7일 확장 실험으로 포트폴리오를 완성한다. 오늘은 2쪽을 읽고 13쪽 정상 ALD 또는 21쪽 Etch 기준 실험부터 시작해도 된다.', size=11, leading=18, gap=16)
    g.source('이 문서는 공개 코드의 실제 구현과 재실행한 모델 결과를 바탕으로 작성했다. 실제 Applied Materials·ASML·KLA 장비 매뉴얼이나 사내 교육자료가 아니다.')
    g.text('판본 1.0  /  2026-09-30<br/>모델: ald-reactive-diffusion-1.0.1 · etch-ar-global-0.1.1<br/>코드·편집에 AI 지원 사용. 학습자의 실험·해석은 별도 기록한다.', size=8.8, leading=14, color=MUTED)

    # 02
    g.page('START HERE', '이 책과 시뮬레이터 사용법', '설명, 가정, 계산 결과, 실제 장비의 증거를 구분해서 읽는다.')
    g.table(['읽을 곳', '내용', '완료할 산출물'], [
        ['3-4쪽', '14일 계획 + 7일 확장', '매일 1개의 설명 또는 실험 기록'],
        ['5-8쪽', '반도체 공정 기초', '전체 흐름과 공정 간 영향 지도'],
        ['9-15쪽', 'ALD 수식·검증·배기 실험', '공급/수송/반응을 구분한 해석'],
        ['16-23쪽', 'Etch 수지·품질·RF 실험', '규격 판정과 보상/복구의 구분'],
        ['24-28쪽', 'DOE·계측·타 직무 연결', '가설을 구분하는 실험계획'],
        ['29-32쪽', '풀이·면접·출처', '숫자와 한계가 있는 설명'],
    ], [70, 193, CW - 263])
    g.head('화면에서 해야 할 순서')
    g.text('공정 평가에서 규격을 확인한다 → 입력값과 고장을 설정한다 → Run simulation을 누른다 → 시간 재생과 종점 값을 구분해 읽는다 → 수식·원리를 확인한다 → 기준 조건과 비교한다 → 평가 보고서 JSON과 실험 메모를 저장한다.')
    g.box('Observed / Inferred / Assumed / Unknown', '<b>Observed</b>: 코드·실행 출력·계측으로 확인. <b>Inferred</b>: 확인한 사실로부터 도출한 해석. <b>Assumed</b>: 계산을 위해 정한 가정. <b>Unknown</b>: 현재 자료로 판단 불가. 예: “깊이 감소”는 모델 관측, “실제 장비에서도 10% 감소”는 미확인이다.')
    g.head('움직이는 화면의 의미')
    g.text('Python이 계산한 시간 응답을 브라우저가 재생한다. 배속은 표시 시간만 바꾸며 물리 계산을 바꾸지 않는다. ALD는 첫 사이클, Etch는 정상 플라즈마 아래 표면 변화다. 보라색 빛과 입자 이동은 설명용 효과이며 RF 진동·광방출·입자 궤적 계산이 아니다.')
    g.source('공개 실행: https://trx1200.github.io/pse-process-recovery-lab/ · 로컬: http://127.0.0.1:8765 · 구현 설명 [C1-C5], 출처표 32쪽. 공개 사이트는 Python을 브라우저에서 실행한다.')

    # 03
    g.page('LEARNING PLAN / WEEK 1', '첫 주: 공정 언어를 되찾기', '매일 이론 35분 + 직접 계산/실험 40분 + 자기 설명 15분. 필요하면 30분 복습.')
    g.table(['날짜', '학습과 실험', '그날 남길 증거'], [
        ['Day 1', '5-6쪽: 증착-노광-식각-계측을 손으로 그린다. 2쪽 화면 순서로 정상 실행.', '공정 흐름 1장 + baseline JSON'],
        ['Day 2', '7-8쪽: Pa, mTorr, sccm, nm/min을 변환. 29쪽 문제 1-2 풀이.', '단위 계산 3개 + 용어 10개'],
        ['Day 3', '9쪽: ALD를 0.5배속 재생. A/B 주입과 성장 시작 시점 확인.', '분압·성장 그래프와 3문장 해석'],
        ['Day 4', '10-11쪽: 분압-확산-피복률을 연결. pulse A를 줄여 예측과 비교.', '실행 전 예측 + 관측 차이'],
        ['Day 5', '12-13쪽: 초기조건·경계조건·포화 조건 설명. baseline 재현.', '36셀 의미와 모델 한계 3개'],
        ['Day 6', '14쪽: 배기 지연을 넣고 퍼지 시간을 보상. 규격을 고정해 평가.', '정상/이상/보상 3조건 표'],
        ['Day 7', '15쪽: 공급 부족과 수송 제한 구분 실험 설계. 1주차를 소리 내어 설명.', '원인 후보 2개 + 구분 실험 1개'],
    ], [53, 272, CW - 325], size=9.5)
    g.box('매일 끝내기 전 네 문장', '① 어떤 요구사항을 확인했나? ② 내가 바꾼 것은 무엇인가? ③ 어떤 상태를 거쳐 결과가 달라졌나? ④ 계산하지 않은 것은 무엇인가? 이 네 문장을 쓸 수 있으면 그날의 공부는 끝이다.')
    g.text('처음부터 모든 고급 계수를 바꾸지 않는다. Recipe를 먼저 이해하고, Chamber로 원인 가설을 넓힌 뒤, Advanced는 계수 불확실성·민감도 실험에 사용한다. 화면에 있는 모든 입력이 실제 장비에서 독립 조작 가능한 손잡이는 아니다.', size=10, leading=16)

    # 04
    g.page('LEARNING PLAN / WEEK 2 + 3', '둘째 주: 원인과 조치를 설명하기', 'Etch 품질을 여러 지표로 판단하고, 자기 프로젝트로 마무리한다.')
    g.table(['날짜', '핵심 활동', '완료 기준'], [
        ['Day 8', '16-17쪽: 식각 품질과 플라즈마 수지', '전력·밀도·온도를 구분해 설명'],
        ['Day 9', '18-20쪽: 이온 에너지·피복률·선택비', '바이어스와 소스 전력 차이 설명'],
        ['Day 10', '21-23쪽: RF 고장·시간 보상·고바이어스', '4조건 비교표 + 조치의 비용'],
        ['Day 11', '24쪽: 2×2 실험 설계와 상호작용', '고정 입력·실행 순서·평가지표 명시'],
        ['Day 12', '25-27쪽: 계측·ASML·KLA 연결', '추가로 필요한 측정 3개 선정'],
        ['Day 13', '28-30쪽: 기록 정리·문제 풀이', '실행 ID가 있는 실험 노트'],
        ['Day 14', '31쪽: 5분 발표 + 2분 질문', '내가 한 일/AI 지원/미검증 구분'],
    ], [52, 254, CW - 306], size=9.5)
    g.head('Day 15-21: 선택 확장')
    g.table(['기간', '추가 작업'], [
        ['15-16일', '문헌의 동일 형상·변수 정의를 확인하고 곡선 1개 재현 계획. 계수를 맞춘 자료와 평가 자료를 분리한다.'],
        ['17-18일', 'ALD 격자/허용오차 또는 Etch 계수 민감도 조사. 결론이 작은 가정 변화에도 유지되는지 확인한다.'],
        ['19-20일', '관측만 보고 후보 고장을 추리는 실험. 고장 이름을 숨긴 기록을 다른 사람이 준비한 경우에만 블라인드라고 표현한다.'],
        ['21일', '결과 2장, 모델 한계 1장, 다음 검증 1장으로 포트폴리오 정리. 자료와 실행 설정을 Git에 함께 남긴다.'],
    ], [74, CW - 74], size=9.3)
    g.source('이 일정은 학습 제안이다. 특정 회사 합격 수준이나 장비 운전 자격을 보증하는 교육과정이 아니다.')

    # 05
    g.page('FOUNDATION / 01', '한 층을 만드는 공정의 연결', '반도체 공정은 각 단계의 성공뿐 아니라 다음 단계가 받을 조건을 맞추는 일이다.', 'BASIC')
    g.eq(['표면 준비 → 박막 형성 → 레지스트/노광/현상', '→ 패턴 전사(Etch) → 제거·세정 → 계측 → 다음 층'], '개념 흐름이다. 실제 순서와 반복 횟수는 소자 구조·재료·통합 공정에 따라 달라진다. [R1]')
    g.table(['공정', '바꾸는 것', '뒤 공정으로 전달되는 문제'], [
        ['증착', '두께, 조성, 계면, 피복성', '두께 편차 → 식각 여유·노광 조건 차이'],
        ['노광/현상', '레지스트의 열린 위치와 크기', '마스크 CD·형상 → 전사할 패턴 변화'],
        ['식각', '열린 부분의 제거량과 형상', '잔사·과식각·측벽 → 연결/누설 문제'],
        ['주입/열처리', '불순물 분포와 전기적 활성', '열 이력·확산 → 구조/재료 제약'],
        ['평탄화/세정', '높이 차·잔류물·표면 상태', '스크래치·오염 → 다음 막의 핵생성'],
        ['계측/검사', '상태를 데이터로 관찰', '샘플링·오차 → 잘못된 조치 위험'],
    ], [78, 150, CW - 228])
    g.head('장비 이상과 유입 웨이퍼 이상을 구분한다')
    g.text('식각 후 잔막이 늘었다고 바로 식각 장비를 원인으로 확정하지 않는다. 전 단계 막이 두꺼워졌는지, 패턴의 열린 면적이 달라졌는지, 측정 위치가 달라졌는지부터 비교한다. 정상 웨이퍼와 문제 웨이퍼의 유입 조건을 맞추면 가설 수를 줄일 수 있다.')
    g.box('자기 설명 문제', '“ALD 두께가 10% 증가하면 Etch 시간을 10% 늘리면 된다”는 주장에 무엇이 빠졌는가? 막의 조성·밀도에 따른 제거율, 위치별 두께, 초기 과도응답, 마스크 손실·정지층 손상, 공정 시간 제약을 함께 확인해야 한다.')
    g.source('전체 반복 공정 개요: ASML 제조 공정 설명 [R1]. 인과 질문과 표는 이 학습 프로젝트의 정리다.')

    # 06
    g.page('FOUNDATION / 02', '재료·표면·계면을 먼저 생각한다', '같은 두께라도 같은 막은 아니다. 수치로 보이지 않는 품질을 질문하는 습관.', 'BASIC')
    g.head('소자에서 막이 맡는 역할')
    g.text('도체는 연결 경로, 절연체는 전기적 분리, 반도체는 제어 가능한 전도 특성을 제공한다. 필요한 기능이 다르면 같은 공정에서도 평가 항목이 달라진다. 이 프로젝트는 특정 게이트 절연막이나 금속 배선의 전기적 성능을 예측하지 않는다.')
    g.table(['관점', '왜 중요한가', '확인할 데이터 예'], [
        ['표면 상태', '흡착 자리·오염·이전 처리에 따라 초기 성장이 달라질 수 있다.', '전처리 이력, 초기 사이클 성장'],
        ['막의 내부', '두께만 같아도 조성·밀도·결함이 다르면 기능과 제거율이 다를 수 있다.', '조성, 굴절률/밀도, 전기 특성'],
        ['계면', '얇은 반응층과 잔류 오염이 전체 소자에 영향을 줄 수 있다.', '계면 분석, 누설, 접촉 저항'],
        ['형상', '입구와 깊은 곳의 반응물 도달량이 다르다.', '단면 두께, 깊이별 조성'],
        ['열 이력', '온도와 노출 시간이 여러 층의 상태를 바꾼다.', '설정/실제 온도, 시간 기록'],
    ], [70, 222, CW - 292], size=9.5)
    g.head('설정값과 실제값의 차이')
    g.text('히터 설정 200 °C가 표면 모든 위치의 온도 200 °C를 뜻하지 않는다. 이 모델은 실제 온도를 하나의 균일 값으로 축약한다. heater_drift 강도 0.35이면 200 - 60×0.35 = 179 °C를 넣는다. 이 숫자는 고장 모델의 정의이며 센서 보정식이나 실제 장비 오프셋 자료가 아니다.')
    g.box('석사 수준으로 설명할 지점', '“온도를 올리면 반응이 빨라진다”에서 멈추지 말고, 어떤 반응 경로·활성화 에너지·수송·탈착을 고려했는지 설명한다. 현재 ALD 모듈에는 탈착·응축·열분해가 없으므로 실제 ALD window를 도출했다고 말할 수 없다.')
    g.source('재료 역할의 기초 [R1]. 모델 실제 온도 정의와 누락 물리: [C1].')

    # 07
    g.page('FOUNDATION / 03', '압력·유량·시간을 섞지 않는다', '단위가 틀리면 정교한 모델도 의미를 잃는다.', 'BASIC + CALC')
    g.table(['물리량', '뜻', '이 프로젝트의 약속'], [
        ['압력 Pa / mTorr', '단위 부피 내 입자 상태와 충돌 환경', 'Etch 총압 20 mTorr = 2.66645 Pa'],
        ['분압 Pa', '혼합 기체 중 한 종의 압력 기여', 'ALD A/B 입력은 분압, 총압 아님'],
        ['유량 sccm', '정해진 표준 상태로 환산한 부피 유량', '273.15 K, 101325 Pa 기준'],
        ['밀도 m⁻³', '단위 부피당 입자 수', '플럭스 m⁻² s⁻¹와 다름'],
        ['노출 Pa·s', '분압의 시간 적분', '밸브 개방 시간만으로 같지 않음'],
    ], [100, 212, CW - 312], size=9.5)
    g.eq(['n_g = p / (k_B T_g)', '1 sccm = [101325 / (k_B × 273.15)] × 10⁻⁶ / 60', '            ≈ 4.478 × 10¹⁷ particles/s'], 'k_B = 1.380649×10⁻²³ J/K. 온도에는 절대온도를 사용한다. [C2]')
    g.head('손계산: 20 mTorr, 350 K')
    g.text('n_g ≈ 2.66645 / (1.380649×10⁻²³×350) = 5.518×10²⁰ m⁻³. 총 유량 100 sccm은 약 4.478×10¹⁹ 입자/s다. R=0.18 m, L=0.10 m이면 V=0.01018 m³, 단순 체류시간 n_g V/유입량은 약 0.125 s다. 이는 모델의 정압·완전혼합 근사이며 실제 배관의 체류시간 분포는 아니다.')
    g.box('자주 틀리는 해석', '유량을 2배로 올려도 압력 제어가 유지되면 압력이 2배가 되는 것은 아니다. 이 모델에서는 압력과 유량을 독립 입력으로 두고 체류시간·반응종 공급을 바꾼다. 실제 장비에서는 배기 밸브·펌프 용량·공급계 응답을 확인해야 한다.')
    g.source('수치와 표준 상태는 Etch 구현 [C2]에서 확인. 반올림된 손계산이며 측정값이 아니다.')

    # 08
    g.page('FOUNDATION / 04', '박막 공정을 선택하는 기준', '막을 만드는 방법과 잘 만들어졌다고 판단하는 방법은 함께 배운다.', 'BASIC')
    g.table(['방식', '학습할 핵심', '먼저 물어볼 품질'], [
        ['PVD', '물질의 물리적 이동과 입사 방향', '두께, 바닥/측벽 도달, 손상'],
        ['CVD', '공급·수송과 표면/기상 반응의 경쟁', '성장률, 조성, 입자, 균일도'],
        ['ALD', '분리된 반응물 주입과 표면 반응의 포화', 'GPC 포화, 깊이별 피복성, 불순물'],
        ['열/플라즈마 활성화', '반응을 활성화하는 에너지 경로 차이', '허용 온도, 반응성, 손상·막질'],
    ], [92, 214, CW - 306], size=9.5)
    g.head('ALD의 장점을 무조건적인 결과로 외우지 않는다')
    g.text('표면 반응이 포화될 수 있어도 반응물이 모든 위치에 충분히 도달했는지는 별도 문제다. 주입을 짧게 하거나 깊고 좁은 구조를 쓰면 깊은 곳의 성장이 부족할 수 있다. 반대로 퍼지가 불충분하면 반응물이 동시에 존재해 의도한 분리 반응과 다른 성장이 생길 수 있다.')
    g.eq(['GPC = 한 사이클에서 증가한 두께 [nm/cycle]', '두께 투영 = GPC × N', '깊은 곳 피복성 = 깊은 곳 두께 / 입구 쪽 두께 × 100%'], '현재 앱의 입구/깊은 곳은 첫/마지막 공간 셀 중심이다. 기하학적 경계면의 정확한 값과 다르다. [C1]')
    g.head('품질 평가의 세 층')
    g.bullets(['막의 양: 목표 두께·GPC·균일도·피복성.', '막의 성질: 조성·밀도·결함·응력·전기 특성. 현재 앱은 계산하지 않는다.', '생산성: 사이클 시간뿐 아니라 이송·세정·안정화·가동률까지 필요하다. 현재 앱은 공정 시간만 제공한다.'])
    g.box('확인 질문', 'GPC가 커졌는데 왜 나쁜 결과일 수 있을까? 목표 두께 초과, 깊은 곳 피복성 저하, 분압 중첩, 막질 변화 가능성을 함께 살핀다. 두께 증가만으로 공정 개선이라고 판단하지 않는다.')
    g.source('ALD 수송-반응 결합의 배경 [R2], 현재 모델의 정의와 평가 [C1, C3].')

    # 09
    g.page('ALD / 01', '한 사이클의 상태를 따라가기', 'A가 자리를 채우고, B가 반응하여 표면 상태를 바꾸는 두 상태 모델.', 'BASIC → ADVANCED')
    g.table(['단계', '밸브 입력', '표면에서 일어나는 모델 반응'], [
        ['A pulse · 0-0.5 s', 'A 목표 20 Pa, B 0', '빈 자리에 A가 흡착, θ 증가'],
        ['A purge · 0.5-2 s', 'A/B 0', '분압 감소. 잔류 A 반응은 계속 가능'],
        ['B pulse · 2-2.5 s', 'B 목표 30 Pa, A 0', 'A 종결 자리를 B가 전환, 막 성장'],
        ['B purge · 2.5-4 s', 'A/B 0', '잔류 B 감소. 남은 반응도 진행'],
    ], [123, 135, CW - 258], size=9.6)
    g.head('설정 분압과 실제 분압')
    g.eq(['dP_i/dt = (u_i - P_i) / τ_i', 'P_i(t) = u_i + [P_i(0) - u_i] exp(-t/τ_i)'], 'u_i: 밸브 목표 분압, P_i: 챔버 분압, τ_i: 공급 또는 배기 시정수. [C1]')
    g.text('정상 τ=0.15 s이면 A pulse 0.5초 후 P_A=20×[1-exp(-0.5/0.15)]≈19.29 Pa다. 밸브가 꺼지는 순간 기체가 사라지는 것은 아니다. 그 뒤 1.5초 퍼지하면 남는 비율은 exp(-1.5/0.15)=exp(-10)≈0.0000454다.')
    g.box('화면에서 직접 볼 것', 'A pulse에서는 A 분압과 피복률이 먼저 올라가는지, B pulse 이후 막이 성장하는지 관찰한다. 일시정지 후 t=0.5, 2.0, 2.5, 4.0 s를 비교한다. 공간 프레임은 계산 결과의 보간이며 N회 총막이 자라는 영상이 아니다.')
    g.text('θ는 A 종결된 자리의 비율이다. 막 두께와 같은 값이 아니다. B가 반응하면 θ는 줄어도 막 두께는 늘 수 있다. “피복률 감소 = 막이 사라짐”으로 읽으면 안 된다.', size=10.5, leading=16.5)
    g.source('기본 레시피·챔버 해석식·상태 의미: [C1].')

    # 10
    g.page('ALD / 02', '기체가 깊은 곳에 도달하는 법', '수송과 표면 소모를 동시에 계산해야 입구만 잘 자라는 상황을 이해할 수 있다.', 'ADVANCED')
    g.eq(['v̄_i = sqrt[8 k_B T / (π m_i)]', 'D_i = (2H/3) v̄_i', '∂p_i/∂t = D_i ∂²p_i/∂x² - (2 q k_B T/H) r_i'], 'H: 두 평판 간격 [m], D_i: Knudsen 확산계수 [m²/s], q: 표면 자리 밀도 [m⁻²], r_i: 자리당 반응률 [s⁻¹]. [C1]')
    g.table(['항', '물리적 의미', '단위 확인'], [
        ['D ∂²p/∂x²', '기체가 고압 쪽에서 저압 쪽으로 공급', '(m²/s)×(Pa/m²) = Pa/s'],
        ['(2qk_BT/H)r', '두 벽의 표면 반응이 기체를 소모', '(m⁻³×J)×s⁻¹ = Pa/s'],
        ['x=0', '챔버와 연결된 입구', 'p_i(0,t)=P_i(t)'],
        ['x=L', '막힌 끝의 무유속 조건', '∂p_i/∂x=0'],
    ], [113, 214, CW - 327], size=9.3)
    g.head('형상 변화가 만드는 두 가지 불리함')
    g.text('간격 H가 작아지면 이 모델의 D는 작아지고, 단위 기체 부피에 대한 벽 소모 계수 2qk_BT/H는 커진다. 깊이 L이 커지면 수송 거리가 길어진다. 따라서 같은 챔버 분압이라도 깊은 곳의 노출은 부족해질 수 있다. 입구 분압만으로 깊은 곳 포화를 보증할 수 없다.')
    g.box('Knudsen 가정의 확인', '벽과의 충돌이 기체 간 충돌보다 우세한 상황을 전제로 한다. 실제 총압·충돌 단면적을 모르면 분압 값 하나만으로 이 가정을 검증할 수 없다. 현재 모델은 캐리어 가스와 점성 유동을 풀지 않는다.', warning=True)
    g.source('수송-표면 소모 결합은 Ylilammi 등(2018) [R2]를 참고. 위 식·경계조건은 이 프로젝트의 구현 [C1]. 논문의 피팅 결과를 복제한 모델은 아니다.')

    # 11
    g.page('ALD / 03', '표면 반응식과 포화의 의미', '반응률이 줄어드는 이유와 성장량이 증가하는 이유를 상태변수로 읽는다.', 'ADVANCED')
    g.eq(['κ_i = s_i(T) / [q sqrt(2π m_i k_B T)]', 'r_A = κ_A p_A (1-θ),     r_B = κ_B p_B θ', 'dθ/dt = r_A - r_B,       dz/dt = r_B', 'film(x) = g_sat × z(x)'], 'κ_i는 반응 계수 [Pa⁻¹ s⁻¹]다. Boltzmann 상수 k_B와 구분하려고 본문에서는 κ를 쓴다. 소스의 k_a/k_b와 같은 항이다.')
    g.text('A만 충분히 공급하면 빈 자리 1-θ가 줄어 A 흡착이 포화된다. B가 도달하면 θ를 줄이면서 z를 증가시킨다. 잘 분리된 충분한 주입은 대략 한 번의 전환 z≈1을 만든다. A와 B가 동시에 남으면 A→B→A 전환이 반복되어 z&gt;1이 가능하다.')
    g.eq(['s_i(T) = s_i(T_ref) exp[-E_a/k_B × (1/T - 1/T_ref)]', 'T_ref = 473.15 K;   입력 E_a [eV]는 J로 변환'], '확산계수와 반응 확률 모두 온도에 의존하지만 다른 함수 형태를 가진다. [C1]')
    g.head('모델 계수와 실제 레시피를 구분한다')
    g.text('s_i, q, E_a, g_sat는 재료·표면 상태를 묶어 표현한 유효 계수다. 현재 기본값은 실제 재료를 식별하거나 측정 곡선에 맞춘 값이 아니다. 두께 곡선 하나에 여러 계수 조합이 맞을 수 있으므로, 좋은 피팅만으로 올바른 반응 기구를 증명하지 못한다.')
    g.box('가설 구분을 위한 추가 데이터', '주입 시간에 따른 포화 곡선, 온도별 곡선, 서로 다른 채널 깊이·간격의 두께 분포를 함께 본다. 모든 데이터를 같은 계수로 설명하는지 확인하고, 계수를 맞춘 자료와 검증 자료를 분리한다.')
    g.source('현재 구현 [C1], 관련 수송-반응 모델 접근 [R2]. 실제 CVD 속도·조성·ALD window는 현재 출력에서 판단할 수 없다.')

    # 12
    g.page('ALD / 04', '수치해가 맞는지 어떻게 확인할까', '방정식이 그럴듯한 것과 코드가 정확한 것, 실제 공정과 맞는 것은 서로 다른 검증이다.', 'ADVANCED')
    g.table(['검증 층', '검사 방법', '말할 수 있는 범위'], [
        ['구현', '입력 범위, NaN/inf, 출력 단위·형식', '코드가 정의한 입력/출력을 지킨다'],
        ['수치', '0 주입, 해석적 배기, 포화, 격자·허용오차', '선택한 사례에서 해의 일관성을 확인'],
        ['모델', '독립 문헌/계측의 같은 조건과 비교', '해당 범위의 물리 정확도를 평가'],
        ['현장', '장비 반복성·막질·고객 규격과 확인', '실제 공정 적용성을 판단'],
    ], [67, 220, CW - 287], size=9.4)
    g.head('현재 계산 설정')
    g.text('x 방향 36개 균일 셀로 압력을 유한체적 이산화한다. 입구는 반 셀 거리의 Dirichlet 조건, 끝은 무유속이다. 초기 분압·θ·z는 0이다. 각 주입/퍼지 구간은 SciPy BDF로 풀며 rtol=2×10⁻⁷, atol=10⁻⁹를 사용한다. 표시 프레임 수가 수치해석기의 내부 시간 스텝 수는 아니다.')
    g.head('본인이 해야 할 최소 검증')
    g.bullets(['A 또는 B 공급을 0으로 두었을 때 의미 있는 막 성장이 사라지는지 확인한다.', '퍼지 중 챔버 압력을 P(0)exp(-t/τ)와 비교한다.', '36셀과 더 촘촘한 셀의 깊이별 두께·끝 두께를 비교한다. 상대오차의 분모가 0 근처면 절대오차를 쓴다.', '날카로운 전선이 생기는 낮은 노출/높은 종횡비도 검토한다. 기본 조건 1개의 수렴으로 모든 입력을 보증하지 않는다.'])
    g.box('중요한 제한', 'cycles는 첫 사이클 결과의 선형 배수다. 실제로 50번 적분하지 않는다. 잔류 상태·간격 축소·핵생성 지연을 매 사이클 갱신하지 않으므로 그 효과를 검증한 시뮬레이터라고 표현할 수 없다.', warning=True)
    g.source('소스 sim_app/models/ald.py 및 test_ald.py [C1, C6]. 로컬 검증 명령: python -m unittest sim_app.tests.test_ald -v')

    # Remaining pages are implemented in append_pages for readability.
    append_pages(g, runs)
    g.save()
    qa = ROOT / 'local' / 'pdf_qa'
    qa.mkdir(parents=True, exist_ok=True)
    (qa / 'layout.json').write_text(json.dumps(g.layout, indent=2), encoding='utf-8')
    summary = {'pages': g.n, 'output': str(output), 'runs': {k: v['run_id'] for k, v in runs.items()},
               'minimum_bottom_y': min(x['bottom_y'] for x in g.layout)}
    (qa / 'build_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


def append_pages(g, runs):
    # 13
    g.page('LAB A0 / BASELINE', '첫 실험: 정상 ALD를 재현한다', '먼저 같은 입력이 같은 결과를 만드는지 확인하고 그래프의 뜻을 설명한다.', 'HANDS-ON')
    g.text('A 0.5 s / purge 1.5 s / B 0.5 s / purge 1.5 s, 분압 A 20 Pa·B 30 Pa, 200 °C, 50 cycles, L=40 μm, H=0.2 μm, 고장 없음. 나머지는 서버 기본값을 유지한다.')
    ap = series(runs['ald_baseline'], 'pressure')
    g.chart([(ap['lines'][0]['name'], ap['x'], ap['lines'][0]['values'], TEAL),
             (ap['lines'][1]['name'], ap['x'], ap['lines'][1]['values'], BLUE)],
            'time (s)', 'pressure (Pa)', '그림 1. 실제 모델 출력의 챔버 A/B 분압. 단계 경계에서 압력이 순간적으로 0으로 사라지지 않는다.', height=194)
    b = runs['ald_baseline']
    g.table(['계산 지표', '재실행 결과', '읽는 방법'], [
        ['입구 쪽 투영 두께', f"{metric(b,'top_thickness_nm'):.4f} nm", '첫 사이클 성장 × 50'],
        ['GPC / 깊은 곳 비율', f"{metric(b,'gpc_nm'):.6f} / {metric(b,'conformality_pct'):.4f}%", '성장량과 깊이 방향 피복성을 구분'],
        ['분압 중첩 / 종료 잔류', f"{metric(b,'overlap_pa_s'):.6f} Pa·s / {metric(b,'residual_pressure_pa'):.6f} Pa", '분리 반응의 유지 여부를 관찰'],
    ], [120, 185, CW - 305], size=9)
    g.box('직접 답할 질문', 'B 주입 전에는 왜 막이 거의 자라지 않는가? θ가 감소하는데 막 두께가 증가할 수 있는 이유는? 첫 사이클 말에 기체·표면 상태가 완전히 초기화되지 않으면 50회 투영에 어떤 오차가 생길까?')
    g.source(f"2026-09-30 현재 코드로 재실행. run_id={b['run_id']}. 관측값은 가상 실험이며 실제 ALD 막의 계측값이 아니다. [C1, C4]")

    # 14
    g.page('LAB A1 / PURGE', '배기 이상을 퍼지로 보상하면?', '두께와 피복성을 회복해도 시간이 허용되지 않을 수 있다.', 'HANDS-ON')
    g.text('고장 purge_restriction, 강도 0.35를 선택한다. 배기 시정수는 0.15×(1+8×0.35)=0.57 s다. 보상 조건은 같은 고장을 둔 채 A/B 뒤 퍼지를 각각 6 s로 늘린다.')
    g.table(['지표', '정상', '배기 이상', '퍼지 6 s씩'], [
        ['투영 두께 nm', '5.0012', '13.7914', '5.0035'],
        ['깊은 곳/입구 %', '99.9760', '36.9476', '99.9309'],
        ['중첩 Pa·s', '0.000131', '0.762618', '0.000295'],
        ['종료 잔류 Pa', '0.001313', '2.123473', '0.000776'],
        ['사이클 시간 s', '4', '4', '13'],
    ], [135, 120, 120, CW - 375], size=9.3)
    profiles = [(label, series(runs[key], 'profile'), color) for label,key,color in [
        ('정상', 'ald_baseline', TEAL), ('배기 이상', 'ald_purge_restriction', ORANGE),
        ('퍼지 보상', 'ald_longer_purge', BLUE)]]
    g.chart([(label,s['x'],s['lines'][0]['values'],color) for label,s,color in profiles],
            'channel depth (μm)', 'projected thickness (nm)',
            '그림 2. 첫 사이클 × 50 투영. 배기 이상에서는 잔류가 커 투영 자체의 적용성도 약해진다.', height=170)
    g.box('판정', '연습 규격은 5±0.5 nm, 깊은 곳 비율 ≥95%, 중첩 ≤0.02 Pa·s, 잔류 ≤0.01 Pa, 사이클 ≤6 s다. 보상 조건은 앞의 4항목을 충족하지만 <b>13 s로 시간 규격 미달</b>이다. 정상 대비 3.25배의 사이클 시간이 필요하고 배기 이상은 남아 있다.')
    g.source('실행 ID: 정상 cb8d81257c08 / 이상 9f213d3b0556 / 보상 c468b5942f8b. [C1, C3, C4] 규격은 학습 예제다.')

    # 15
    g.page('LAB A2 / DISCRIMINATION', '공급 부족인가, 수송 제한인가?', '한 개의 부족한 두께 값만으로 원인을 하나로 정할 수 없다.', 'EXPERIMENT DESIGN')
    g.table(['가설', '예상되는 관측', '구분할 실험'], [
        ['A 공급 부족', '챔버 A 분압 또는 노출 감소. 깊은 곳의 포화 부족 가능.', '설정값이 아닌 실제 분압 이력 비교'],
        ['깊은 구조의 수송 제한', '같은 챔버 압력인데 깊이에 따라 성장 감소.', '주입 시간과 L/H를 따로 변경'],
        ['표면 반응성 변화', '동일 공급에도 포화 속도·분포가 달라짐.', '온도/반응 계수 민감도와 독립 표면 정보'],
        ['측정/샘플링 차이', '다른 위치를 비교해 보이는 두께 차이.', '같은 위치·동일 방법으로 재측정'],
    ], [95, 207, CW - 302], size=9.5)
    g.head('실행할 작은 행렬')
    g.text('기준 조건에서 A pulse를 0.1, 0.3, 0.5, 1.0 s로 바꾼다. 다음에는 A pulse를 고정하고 depth를 20, 40, 80 μm로 바꾼다. 각 실행의 입구/깊은 곳 성장, 중첩, 잔류, 사이클 시간을 함께 저장한다. 공급 저하 고장 실험은 별도로 두어 변경 원인을 섞지 않는다.')
    g.box('실행 전 예측을 먼저 적는다', '“A 노출을 늘리면 부족한 깊은 곳의 성장은 회복될 수 있다. 이미 포화된 입구의 성장 변화는 작을 것이다. 다만 중첩과 초기화 조건을 유지해야 한다.” 이 예측이 틀리면 분압 이력과 반응 전선을 다시 보고 설명을 수정한다.')
    g.head('입증하지 못한 것')
    g.text('이 실험만으로 특정 전구체의 반응 확률이나 실제 장비의 공급 고장을 식별한 것은 아니다. 실제 적용에서는 유입 전구체 상태·온도·배관·계측·막 조성 등 추가 관측이 필요하다. 이 페이지의 방향성은 조건부 가설이며 아직 실행한 결과표가 아니다.')
    g.source('모델에서 직접 조절 가능한 키: pulse_a_s, depth_um, pressure_a_pa, sticking_a. 고장: precursor_starvation. [C1]')

    # 16
    g.page('ETCH / 01', '잘된 식각을 먼저 정의한다', '원하는 재료를 원하는 만큼 제거하면서 남겨야 할 재료와 형상을 지킨다.', 'BASIC')
    g.table(['평가 축', '질문', '현재 앱 계산 여부'], [
        ['깊이·제거율', '덜 깎였나, 지나치게 깎였나?', '평균 깊이·정상 제거율 계산'],
        ['면내 균일도', '중앙과 가장자리 차이가 허용되는가?', '가정한 방사형 플럭스로 계산'],
        ['마스크·선택비', '타깃 제거 중 보호층을 얼마나 잃었나?', '일반화한 수율 모델로 계산'],
        ['CD·측벽·ARDE', '폭·각도·깊은 패턴의 속도가 맞는가?', '미구현'],
        ['손상·잔사·막질', '기능을 해치거나 후속 공정을 방해하나?', '미구현'],
        ['반복성·생산성', '웨이퍼/장비/시간에 걸쳐 유지되는가?', '실측 반복성·전체 처리량 미구현'],
    ], [107, 213, CW - 320], size=9.3)
    g.head('제거 메커니즘을 나누어 본다')
    g.text('물리적 스퍼터는 입자의 에너지 전달, 화학적 제거는 표면 반응과 생성물 제거, 이온 보조 반응은 이온과 흡착종의 결합 효과를 표현한다. 현재 모델은 이를 서로 다른 항으로 합친다. 실제 재료의 부산물 휘발성·측벽 보호막·반응망은 직접 풀지 않는다.')
    g.box('공정 평가 화면의 합격 문구', '“계산 가능한 항목 충족”은 앱이 계산한 지표가 사용자가 정한 구간에 들어왔다는 뜻이다. 패턴 형상·손상·수율까지 검증한 공정 합격이 아니다. 계산하지 않은 중요한 품질은 별도 평가 계획에 남긴다.')
    g.text('같은 평균 깊이라도 면내 분포가 다를 수 있고, 같은 제거율이라도 마스크 소모가 다를 수 있다. 총점 하나로 상쇄하지 말고 요구사항을 항목별로 판정한다. 부적합 지표가 하나라도 있으면 그 영향과 허용 여부를 구체적으로 검토한다.', size=10.2, leading=16.1)
    g.source('계산 가능/불가능 항목과 판정 구현 [C2, C3]. 실제 장비나 재료의 범용 합격 규격을 제시한 것이 아니다.')

    # 17
    g.page('ETCH / 02', '플라즈마의 입자 수지와 전력 수지', '전자온도와 전자밀도는 역할이 다른 계산 상태다.', 'ADVANCED')
    g.eq(['P_abs = P_forward × (1-r) × η × duty', 'n_Ar k_iz(T_e) = u_B A_eff / V', 'u_B = sqrt(e T_e / m_Ar)', 'P_abs = n_e e u_B A_eff E_pair + P_dissociation'], 'r: 반사율, η: 결합 효율. T_e와 E_pair는 eV, n_e는 m⁻³. e는 eV를 J로 바꾸는 전하량 수치이기도 하다. [C2]')
    g.text('입자 수지는 전자 1개당 이온화 생성률과 경계 손실률의 균형이다. 여기서 T_e를 먼저 구한다. 전력 수지는 전자-이온 쌍 생성과 벽 손실·해리에 쓰는 전력을 합해 n_e를 구한다. 이 모델의 T_e가 소스 전력과 직접 연결되지 않는 이유는 첫 수지에서 밀도가 상쇄되기 때문이다.')
    g.table(['정상 기본 조건', '현재 계산값', '해석'], [
        ['흡수 전력', '432 W', '600×(1-0.04)×0.75×1'],
        ['전자온도 T_e', '2.2721 eV', '평균 에너지 분포를 축약한 상태'],
        ['전자밀도 n_e', '2.4960×10¹⁷ m⁻³', '에너지 공급과 손실의 균형'],
        ['이온 플럭스', '9.0919×10¹⁹ m⁻² s⁻¹', '단위 면적·시간에 도달하는 입자 수'],
    ], [134, 154, CW - 288], size=9.3)
    g.box('적용 범위', 'Ar 속도계수의 1-7 eV 범위에 입자 수지의 근이 없으면 outside_rate_fit이다. 표시되는 0을 실제 방전 꺼짐으로 해석하지 않는다. 점화·소멸·E/H 모드 전환·비맥스웰 전자분포는 계산하지 않는다.', warning=True)
    g.source('속도계수 배경 Kim(2006) [R3]. 수지·경계 손실·계수 출처와 구현의 구분은 docs/ETCH_MODEL.md [C2]에 상세히 기록한다.')

    # 18
    g.page('ETCH / 03', '소스 전력과 바이어스는 다르다', '입자 수를 늘리는 것과 각 입자에 전달하는 에너지를 바꾸는 것을 구분한다.', 'ADVANCED')
    g.eq(['Γ_i = h_L n_e u_B', 'V_s = |V_bias| + 0.5 T_e ln[m_Ar/(2πm_e)]', 's_CL = sqrt[(4/9) ε₀ sqrt(2e/m_Ar) V_s^(3/2) / (e Γ_i)]', 'E_i = 0.5 T_e + V_s / (1 + s_CL/λ_i)'], 'V_bias 입력은 음의 바이어스 크기의 절댓값이다. λ_i=1/(n_g σ_i). 마지막 충돌 감쇠식은 이 프로젝트가 선택한 축약 가정이다. [C2]')
    g.head('왜 바이어스 120 V인데 에너지는 120 eV가 아닌가')
    g.text('모델에는 부유 전위 성분, 쉬스 두께 척도, 이온-중성 충돌 감쇠가 함께 들어간다. 기본 조건의 평균 에너지 근사는 87.10 eV다. 이는 RF 에너지 분포 전체가 아니라 하나의 대표 에너지다. 에너지와 각도 분포를 모르면 패턴 측벽의 상세 거동을 예측할 수 없다.')
    g.table(['변경', '현재 모델에서 직접 바뀌는 경로', '해석 주의'], [
        ['소스 전력 증가', '흡수 전력 → 밀도·플럭스 → 표면 제거', 'T_e가 반드시 증가하지 않음'],
        ['바이어스 증가', '쉬스 전위 → 에너지·수율 → 제거/손실', '마스크 손실·손상 가능성 별도'],
        ['압력 증가', '중성 밀도·충돌·입자 수지 전체', '제거율이 단순 단조 함수일 필요 없음'],
    ], [86, 245, CW - 331], size=9.4)
    g.box('연결되지 않은 에너지 경로', '바이어스 전원은 소스 전력 수지와 별도 공급으로 두었다. 바이어스가 벌크 전자를 가열하는 효과와 RF 파형·IEDF는 생략했다. 따라서 소스와 바이어스의 모든 상호작용을 재현한다고 표현할 수 없다.')
    g.source('수식·단위·감쇠 근사와 누락 물리 [C2]. 숫자는 정상 기준 재실행 결과 [C4].')

    # 19
    g.page('ETCH / 04', '라디칼 공급에서 식각 깊이까지', '기체는 정상상태로, 표면은 시간에 따라 변하는 준정상 분리 모델.', 'ADVANCED')
    g.eq(['a = sticking × Γ_X / N_s', 'b = k_des + k_chem + Γ_i Y_assist / N_s', 'dθ/dt = a(1-θ) - bθ;   θ(0)=0', 'θ_ss = a/(a+b);   θ(t)=θ_ss [1-exp(-(a+b)t)]'], 'Γ_X: 라디칼 플럭스 [m⁻² s⁻¹], N_s: 표면 자리 밀도 [m⁻²]. a,b는 s⁻¹이다. [C2]')
    g.eq(['J_target = (N_s k_chem + Γ_i Y_assist)θ + Γ_i Y_sputter', 'depth(t) = ∫ J_target dt / N_target', 'mask_depth(t) = Γ_i Y_mask t / N_mask'], 'J는 제거 입자 수 플럭스. 원자밀도 [m⁻³]로 나누면 m/s가 되어 깊이를 얻는다. 식각 깊이는 해석적 적분으로 계산한다.')
    g.head('초기에는 왜 깊이가 완전히 직선이 아닐까')
    g.text('처음 θ=0이므로 흡착종을 이용하는 반응 성분이 아직 충분하지 않다. 시간이 지나 θ_ss에 가까워지면 제거율도 정상값에 접근한다. 물리 스퍼터 항은 처음부터 작용할 수 있다. 짧은 시간의 깊이/시간과 정상 제거율은 같지 않을 수 있다.')
    g.box('화학 모델의 경계', 'X₂→2X는 가상의 희석 반응종 모델이다. 라디칼 질량 19 u를 쓴다고 SF₆나 CF₄ 식각 화학을 구현한 것은 아니다. 가스 공급·해리·벽 손실·웨이퍼 소비의 수지는 풀지만 실제 분자 반응망과 음이온 화학은 생략했다.', warning=True)
    g.source('이 식은 프로젝트의 일반화된 표면 가정 [C2]. 초기 표면 반응이 기체 정상상태를 다시 바꾸는 과도 피드백은 포함되지 않는다.')

    # 20
    g.page('ETCH / 05', '공간 평균과 품질 지표 읽기', '평균을 내는 좌표와 선택비의 정의가 바뀌면 숫자의 의미도 바뀐다.', 'ADVANCED')
    g.eq(['q = r² / R_wafer²', 'Γ_i(q) = mean_Γ_i × [1 + α(0.5-q)]', '면적평균 깊이 = ∫₀¹ depth(q) dq', '비균일도 = (최대 깊이 - 최소 깊이)/(2×평균 깊이) × 100%'], 'q는 면적에 균등한 좌표다. r에 균일한 점을 같은 가중치로 평균하면 웨이퍼 면적 평균과 다르다. [C2]')
    g.text('방사형 이온 플럭스 분포는 공간 플라즈마 PDE의 해가 아니라 입력으로 정한 형상이다. 평균이 보존되는 분포를 위치별 표면식에 넣어 깊이를 다시 계산한다. 앱의 시간 곡선은 평균 플럭스의 균일 참고 사례이고, 종점 KPI는 방사형 결과의 면적 평균이어서 소폭 다를 수 있다.')
    g.eq(['정상 선택비 = 정상 타깃 제거율 / 정상 마스크 제거율', '누적 제거량 비 = depth(t) / mask_depth(t)'], '초기 과도응답 때문에 두 비는 완전히 같지 않을 수 있다. 앱의 규격은 정상 선택비에 적용한다. [C2, C3]')
    g.table(['조건', '올바른 처리'], [
        ['깊이 0', '비균일도 분모가 0이므로 좋은 균일도 0%로 처리하지 않는다.'],
        ['마스크 제거율 0', '선택비를 무한 합격으로 처리하지 않고 정의 불가로 표시한다.'],
        ['모델 계산 범위 밖', '평가를 보류하고 범위/가정을 확인한다.'],
        ['입력만 변경', '새 실행 전에는 이전 실행의 종점을 평가한다.'],
    ], [120, CW - 120], size=9.3)
    g.source('지표의 수학적 정의 [C2]. 프런트엔드 assessment.ts의 unavailable/incomplete 처리 [C3].')

    # 21
    g.page('LAB E0 / FOUR CASES', '4조건을 같은 규격으로 비교한다', '현재 코드로 재실행한 결정론적 가상 실험. 모든 값은 실제 계측값과 구분한다.', 'HANDS-ON')
    g.text('기준: 600 W, 20 mTorr, 100 sccm, 가상 반응 가스 분율 0.04, 바이어스 120 V, 60 s. 연습 규격: 깊이 30±3 nm, 비균일도 ≤5%, 마스크 손실 ≤3 nm, 정상 선택비 ≥10, 시간 ≤90 s.')
    g.table(['조건', '깊이 nm', '마스크 nm', '선택비', '시간 s'], [
        ['정상 기준', '28.8548', '2.5948', '11.1262', '60'],
        ['RF 이상 0.35', '25.7830', '1.4833', '17.3965', '60'],
        ['RF 이상 + 70 s', '30.0838', '1.7306', '17.3965', '70'],
        ['정상 + 250 V', '34.8864', '4.7632', '7.3266', '60'],
    ], [137, 94, 95, 91, CW - 417], size=9.1)
    lines = []
    for label, key, color in [('정상','etch_baseline',TEAL),('RF 이상','etch_rf_mismatch',ORANGE),('고바이어스','etch_high_bias',BLUE)]:
        d = series(runs[key], 'depth')
        lines.append((label,d['x'],d['lines'][0]['values'],color))
    g.chart(lines, 'time (s)', 'uniform-flux reference depth (nm)',
            '그림 3. 시간 곡선은 평균 플럭스의 균일 참고 깊이. 표의 면적 평균 깊이와 정의가 약간 다르다.', height=184)
    g.box('판정', '정상은 계산 가능한 5항목 충족. RF 이상은 깊이 부족. 시간을 늘린 보상은 5항목 충족하지만 RF 이상은 유지된다. 고바이어스는 깊이 초과·마스크 손실 초과·선택비 미달이다. 네 조건의 비균일도는 각각 1.3546%, 1.3687%, 1.3682%, 1.8928%다.')
    g.source('실행 ID 순서: 9f29c7512177 / 2fcf769f6d96 / c4d44090db84 / 085d2ad5f1b0. 현재 모델 버전 etch-ar-global-0.1.1. [C4]')

    # 22
    g.page('LAB E1 / RF FAULT', '깊이 감소에서 원인 가설로', '관측 → 상류 상태 → 경쟁 가설 → 구분 실험의 순서를 지킨다.', 'TROUBLESHOOTING')
    g.eq(['r_actual = r + (1-r) × severity', '0.04 + 0.96×0.35 = 0.376', 'P_abs = 600×(1-0.376)×0.75 = 280.8 W'], '기준 432 W에서 흡수 전력이 35% 감소한다. 이 고장은 반사율부터 바꾸고 하류 상태를 다시 계산한다.')
    g.text('같은 60초에서 평균 깊이는 28.8548→25.7830 nm로 약 10.65% 감소한다. 전자밀도는 2.4960×10¹⁷→1.6196×10¹⁷ m⁻³로 감소한다. T_e는 동일하다. 이때 깊이 변화율이 흡수 전력 변화율과 같지 않은 것은 표면 공급·에너지·반응의 비선형 결합 때문이다.')
    g.table(['경쟁 가설', '확인하고 싶은 독립 관측', '구분 논리'], [
        ['RF 전달 이상', 'forward/reflected power, 매칭 상태', '같은 설정 전력에서 전달 상태가 변했는가'],
        ['반응종 공급 저하', '유량 설정/실제값, 공급 이력', 'RF가 정상인데 화학 공급이 바뀌었는가'],
        ['유입 막 변화', '식각 전 두께·조성·패턴 면적', '제거 대상 자체가 달라졌는가'],
        ['측정 편차', '동일 위치 재측정과 기준 샘플', '측정 방법이 차이를 만들었는가'],
    ], [105, 205, CW - 310], size=9.3)
    g.box('이 실험이 증명하는 것', '고장을 알고 주입하고 그 강도를 0으로 되돌리는 것은 모델의 내부 일관성과 조치 효과 확인이다. 원인을 숨긴 관측으로 독립 진단한 것이 아니다. “RF 이상을 시나리오로 주입해 전달 전력-식각량 경로를 분석했다”가 정확한 표현이다.')
    g.source('RF 고장 정의·실행 결과 [C2, C4]. 현장 확인 항목은 문제 해결을 위한 제안이며 실제 장비 접근이나 계측을 수행한 기록이 아니다.')

    # 23
    g.page('LAB E2 / TRADE-OFF', '보상과 복구, 속도와 품질', '한 KPI가 좋아졌다는 이유로 전체 공정이 개선됐다고 말하지 않는다.', 'PROCESS JUDGMENT')
    g.head('시간 60→70 s: 깊이는 회복되지만 무엇이 남나')
    g.text('동일한 RF 이상 아래 평균 깊이가 30.0838 nm로 들어온다. 처리 시간은 16.7% 늘어난다. 흡수 전력 280.8 W와 반사율 0.376은 그대로다. 이는 레시피 보상이며 RF 전달 상태의 복구가 아니다. 동일 시간 제약이 더 엄격한 고객이라면 이 조치는 채택할 수 없을 수 있다.')
    g.head('바이어스 120→250 V: 왜 더 깊이 깎아도 탈락인가')
    g.text('정상 조건에서 에너지가 87.10→140.35 eV로 증가한다. 깊이는 34.8864 nm지만 마스크 손실은 4.7632 nm, 선택비는 7.3266이다. 연습 규격의 깊이 상한 33 nm, 마스크 상한 3 nm, 선택비 하한 10을 모두 벗어난다. 실제 손상까지 증가했는지는 현재 모델로 확인할 수 없다.')
    g.table(['조치', '모델에서 확인한 효과', '남은 질문'], [
        ['시간 연장', '깊이 회복, 동일 RF 상태', '처리량·마스크 여유·지속 사용 가능성'],
        ['바이어스 증가', '빠른 제거, 더 큰 마스크 소모', '손상·CD·측벽·잔사 영향'],
        ['고장 강도 0', '기준 전달 상태와 결과 복원', '실제 원인 부품·재발·복구 검증'],
    ], [94, 226, CW - 320], size=9.4)
    g.box('다음 실험', '목표 깊이에 맞도록 시간을 조절한 뒤에도 마스크 손실과 선택비가 만족되는지 비교한다. “조건별로 같은 시간”과 “조건별로 같은 깊이”의 비교는 서로 다른 질문이다. 비교 기준을 실험 전에 적는다.')
    g.text('규격을 완화해 결과를 합격으로 바꾸면 재평가다. 물리 결과가 바뀌지 않았으므로 공정 개선이라고 기록하지 않는다. 기준 규격과 새 규격을 모두 남겨야 해석을 추적할 수 있다.', size=10.2, leading=16.1)
    g.source('재실행한 모델 수치 [C4]. 판정 규칙 [C3]. 실제 장비 조치의 실행을 권고하는 문서가 아니다.')

    append_final_pages(g, runs)


def append_final_pages(g, runs):
    # 24
    g.page('EXPERIMENT / 01', '조건 탐색을 실험 설계로 바꾸기', '가장 좋은 숫자를 찾기 전에 어떤 질문에 답할 실험인지 정한다.', 'DOE')
    g.head('한 인자씩 바꾸는 탐색의 용도')
    g.text('기준에서 한 입력만 바꾸면 인과 경로를 배우기 좋다. 그러나 여러 인자가 동시에 바뀌는 실제 공정의 상호작용을 충분히 볼 수 없다. 아래는 바이어스와 시간의 2×2 작은 행렬이다. 결과값은 아직 제시하지 않으며 학습자가 직접 실행한다.')
    g.table(['조건', '바이어스 V', '시간 s', '고정할 항목'], [
        ['E1', '100', '50', '600 W, 20 mTorr, 100 sccm'],
        ['E2', '150', '50', '분율 0.04, 고장 없음'],
        ['E3', '100', '70', '형상·모든 Advanced 기본값'],
        ['E4', '150', '70', '같은 규격과 모델 버전'],
    ], [58, 99, 99, CW - 256], size=9.6)
    g.eq(['시간 50 s에서 바이어스 효과: Δ_low = y(E2) - y(E1)', '시간 70 s에서 바이어스 효과: Δ_high = y(E4) - y(E3)', '차이의 차이: Δ_high - Δ_low'], 'y를 깊이, 마스크 손실, 선택비에 각각 적용한다. 수치가 0이 아니면 선택한 범위에서 두 인자의 결합 효과를 확인한 것이다.')
    g.box('결정론 모델에 통계를 억지로 붙이지 않는다', '동일 입력을 반복해도 같은 결과가 나오는 모델이다. 반복 30회를 돌려 표준편차 0이라고 실제 공정 반복성이 완벽하다고 주장하면 안 된다. 관측 잡음·장비 변동의 분포를 별도로 정의하지 않았다면 p값·신뢰구간을 만들 근거가 없다.', warning=True)
    g.text('현장 실험을 계획한다면 웨이퍼/장비 차이, 시간 드리프트, 계측 오차를 고려해 반복·블록·실행 순서를 설계한다. 모델 실험에서는 먼저 입력 조합의 범위와 모델 적용성을 확인하고, 결과가 나쁜 조건도 보존한다.')
    g.source('2×2 행렬과 해석은 본 학습용 제안. 공개 PSE 업무 설명은 가설 실험·DOE·통계 분석·원인 분석을 포함한다 [R4].')

    # 25
    g.page('MEASUREMENT / 01', '계측 없이 공정을 평가할 수 없다', '모델의 정답과 실제로 관측할 수 있는 값 사이에는 측정 과정이 있다.', 'PRACTICE')
    g.table(['측정 질문', '가능한 접근 예', '주의할 점'], [
        ['막 두께·면내 편차', '광학 박막 계측, 위치별 맵', '광학 상수·층 구조 가정에 의존 가능'],
        ['CD·측벽·패턴 깊이', 'CD 계측, 단면 관찰', '샘플링·측정 위치·파괴 여부'],
        ['입자·패턴 결함', '광학/전자빔 검사와 리뷰', '검출 민감도와 오검출의 균형'],
        ['장비 상태', '압력·전력·유량·온도 이력', '센서 교정·응답 지연·동기화'],
    ], [121, 181, CW - 302], size=9.5)
    g.head('규격 한계와 관리 한계를 구분한다')
    g.text('규격은 제품/공정이 요구하는 허용 범위이고, 관리 한계는 안정된 과정의 변동에서 이상 신호를 찾기 위한 기준이다. 모든 측정값이 규격 안에 있어도 한 방향으로 드리프트하면 원인을 확인해야 한다. 반대로 불안정한 데이터를 모아 공정능력을 한 숫자로 요약하면 해석이 왜곡될 수 있다.')
    g.eq(['C_p = (USL - LSL) / (6σ)', 'C_pk = min[(USL-μ)/(3σ), (μ-LSL)/(3σ)]'], '안정된 과정과 분포·독립성 등 적절한 가정이 필요하다. 추정 불확실성도 평가해야 한다. [R5]')
    g.box('이 앱에 Cpk를 붙이지 않은 이유', '현재 모델에는 웨이퍼 반복 측정의 모집단 변동이 없다. 공간의 101개 지점은 독립 웨이퍼 101장이 아니고, 시간 표본도 공정 반복 실험이 아니다. 결정론 결과에 임의 잡음을 더하면 그것은 가정된 잡음 실험으로 따로 표시해야 한다.')
    g.source('계측·검사의 적용 예 [R6]. 공정능력 정의와 통계 전제 [R5]. 표의 데이터 요청은 장비별 실무 절차를 대체하지 않는다.')

    # 26
    g.page('ROLE CONNECTION / ASML', '노광 문제와 식각 문제를 연결하기', 'ASML TSE 준비에서는 공정 결과를 장비 상태와 계측으로 연결하는 연습이 유용하다.', 'CONTEXT')
    g.eq(['CD ≈ k₁ λ / NA'], '노광 해상도의 대표 척도. λ: 파장, NA: 개구수, k₁: 공정·광학 조건을 묶는 계수. 이것 하나로 수율과 실제 패턴 품질을 모두 설명하지 못한다. [R7]')
    g.head('구분해서 배울 세 항목')
    g.bullets(['CD: 원하는 선폭/공간의 크기. 식각 전 레지스트와 식각 후 패턴을 비교한다.', 'Overlay: 이전 층과 새 층의 정렬. 선폭이 맞아도 위치가 틀릴 수 있다.', 'Focus/dose: 초점과 노광량. 패턴 형상과 공정 여유를 함께 보아야 한다.'])
    g.table(['관측', '먼저 나눌 원인', '추가로 필요한 데이터'], [
        ['식각 후 CD 변화', '노광/현상 단계의 유입 CD vs 식각 전사', '동일 위치의 pre/post CD'],
        ['특정 위치의 패턴 문제', '웨이퍼/필드 패턴 vs 장비/공정 공간 패턴', '필드·웨이퍼 좌표가 연결된 맵'],
        ['로트마다 성능 변화', '입고 재료·레시피·장비 상태·계측 조건', '시간 정렬된 로그와 이력'],
    ], [119, 213, CW - 332], size=9.4)
    g.box('현재 프로젝트와의 연결 범위', '이 프로젝트는 광학 노광·정렬·스테이지 제어를 계산하지 않는다. 대신 “상류 입력을 확인하고 관측을 정렬하여 원인을 분리하는 방법”을 연습할 수 있다. TSE 준비에는 해당 직무 공고의 장비·지원 범위에 맞춘 별도 노광/장비 공부가 필요하다.')
    g.text('면접 연습: “식각 후 불량을 발견했는데 왜 노광 데이터를 보나요?” 답: 패턴 전사는 유입 마스크 형상의 영향을 받으므로, 식각 전후 같은 위치의 차이를 비교해야 식각 단계에서 추가된 변화를 분리할 수 있다.')
    g.source('노광의 역할과 계측 피드백 [R1], Rayleigh 식 [R7]. 직무 연결 방법은 작성자의 학습 제안이며 특정 TSE 채용요건을 인용한 것이 아니다.')

    # 27
    g.page('ROLE CONNECTION / KLA', '공정 변화인가, 측정 변화인가?', 'KLA FAE 준비에서는 데이터를 얻는 조건과 고객의 판단 기준을 함께 생각한다.', 'CONTEXT')
    g.head('측정값은 공정 상태의 완전한 복사본이 아니다')
    g.text('검사는 결함 후보를 찾고, 리뷰는 후보의 성격을 더 자세히 확인하며, 계측은 두께·형상 같은 양을 추정한다. 공정 조건이 바뀌면 신호 자체가 달라지고, 측정 모델이나 임계값의 적합성도 달라질 수 있다. 측정 결과를 그대로 원인으로 해석하지 않는다. [R6]')
    g.table(['상황', '확인할 항목', '판단에 필요한 비교'], [
        ['결함 수가 갑자기 증가', '동일 검사 레시피·민감도·샘플링인가?', '원본 신호/이미지와 결함 리뷰'],
        ['막 두께가 달라 보임', '측정 모델·광학 상수·표면 상태인가?', '독립 방법·기준 샘플 비교'],
        ['웨이퍼 가장자리만 이상', '공정 분포인가, edge 제외 범위인가?', '같은 좌표/제외 규칙의 맵'],
        ['장비 간 결과 불일치', '교정·오프셋·반복성·조건이 같은가?', '공통 샘플의 교차 측정'],
    ], [115, 210, CW - 325], size=9.4)
    g.box('이 앱으로 할 수 있는 계측 사고 실험', '동일 모델의 평균 깊이와 한 위치의 깊이를 비교해 본다. 두 값의 차이를 공정 이상이라고 부르기 전에 평균의 정의와 측정 위치를 확인한다. 깊이 0에서 비균일도를 정의 불가로 남기는 이유도 설명해 본다.')
    g.head('고객 문제를 기술 질문으로 바꾸는 예')
    g.text('“수율이 떨어졌다”를 “언제부터, 어떤 제품/층/장비에서, 어떤 결함 분포가, 동일 검사 조건에서 증가했는가”로 바꾼다. 다음 측정이 어느 가설을 구분하는지 설명하고, 필요한 시간·샘플·데이터를 정한다. 이 구조는 AMK PSE의 원인 분석에도 연결된다.')
    g.source('KLA 공식 제조 솔루션에서 검사·리뷰·계측·공정 관리 범위를 확인 [R6]. 구체적인 FAE 배치 업무와 채용요건은 해당 공고를 별도 확인해야 한다.')

    # 28
    g.page('LAB NOTE / TEMPLATE', '증거가 남는 실험 노트', '그럴듯한 설명보다 실행 조건과 반례까지 남긴 기록이 강하다.', 'PORTFOLIO')
    g.table(['항목', '작성 예: RF 전달 이상'], [
        ['요구사항', '깊이 30±3 nm, 비균일도 ≤5%, 마스크 ≤3 nm, 선택비 ≥10, 시간 ≤90 s.'],
        ['Observed', '같은 60 s에서 기준 28.8548 nm → RF 이상 25.7830 nm. P_abs 432→280.8 W.'],
        ['가설', '주입한 반사율 변화로 전력 전달·입자 공급·표면 제거가 변한다. 실제 진단에서는 공급 부족도 후보.'],
        ['구분 실험', '기준·동일 고장·같은 고장+70 s를 비교. RF 유효 상태와 깊이를 동시에 기록.'],
        ['조치와 결과', '70 s에서 30.0838 nm. 5개 계산 지표 충족. RF 전달 상태는 여전히 이상.'],
        ['비용·미검증', '시간 +16.7%. CD·손상·막질·장비 반복성과 실제 고장 원인 미확인.'],
        ['재현 정보', 'etch-ar-global-0.1.1; 2fcf769f6d96 → c4d44090db84. 전체 입력은 JSON 저장.'],
    ], [85, CW - 85], size=9.4)
    g.head('새 실험의 빈 양식')
    g.text('<b>문제:</b> ______　<b>규격:</b> ______　<b>기준 실행 ID:</b> ______<br/><b>변경 입력:</b> ______　<b>고정 입력:</b> ______<br/><b>실행 전 예측:</b> ______　<b>예측을 틀리게 할 관측:</b> ______<br/><b>결과:</b> ______　<b>해석/다른 설명:</b> ______<br/><b>부작용:</b> ______　<b>다음 검증:</b> ______', size=10.2, leading=21)
    g.box('저장해야 할 것', 'Recipe JSON만으로는 평가 규격과 해석이 충분하지 않다. 평가 보고서 JSON에 현재 규격·모델 버전·원 실행·비교 기준·메모가 포함됐는지 확인한다. 나쁜 조건과 실패 결과도 같은 폴더에 보존한다.')
    g.source('실험 예는 모델 결과 [C4], 보고서 구조는 assessment.ts [C3]. AI 지원 코드와 본인의 실험 설계·검토·해석을 함께 표시한다.')

    # 29
    g.page('WORKED ANSWERS / 01', '숫자로 확인하는 다섯 문제', '먼저 직접 계산한 다음 아래 풀이와 단위·가정을 비교한다.', 'SELF-CHECK')
    g.head('1. 20 mTorr를 Pa로 바꾸면?')
    g.text('1 Torr=133.322387415 Pa이므로 20 mTorr=20×10⁻³×133.322387415=2.66645 Pa. 20을 그대로 Pa에 넣으면 약 7.5배의 입력 오류가 된다.')
    g.head('2. 전력 600 W, 반사율 4%, 결합 75%의 흡수 전력은?')
    g.text('600×0.96×0.75=432 W. 결합 효율은 반사 후 전달된 전력에 적용한다. RF 고장 0.35에서는 반사율 0.376으로 변해 280.8 W가 된다. 바이어스 전원 에너지는 여기 포함되지 않는다.')
    g.head('3. τ=0.15 s에서 잔류를 1% 이하로 줄이는 시간은?')
    g.eq(['P(t)/P(0)=exp(-t/τ) ≤ 0.01', 't ≥ τ ln(100) = 0.15×4.60517 ≈ 0.691 s'], '챔버의 단일 지수 배기 가정에서의 상대 잔류다. 깊은 채널이나 표면 상태의 완전 초기화를 보증하지 않는다.')
    g.head('4. 목표 깊이 30 nm, 정상 속도 25.8049 nm/min이면?')
    g.text('단순 정상 속도 환산은 t≈30/25.8049×60=69.75 s다. 초기 표면 과도응답과 공간 평균 차이를 생략한 근사다. 실제 모델을 70 s 실행하면 평균 30.0838 nm가 나온다. 손계산을 출발점으로 삼고 정확한 모델 결과로 다시 판정한다.')
    g.head('5. 평균 30 nm, 최대 31 nm, 최소 29 nm의 비균일도는?')
    g.text('(31-29)/(2×30)×100=3.33%. 분모 정의가 다르면 숫자가 달라지므로 보고서에 정의를 같이 쓴다. 101개 공간 점의 범위를 웨이퍼 간 반복성으로 해석하지 않는다.')
    g.source('1-4번 단위·모델식 [C1, C2]; 5번은 정의 설명을 위한 가상 숫자 예제이며 시뮬레이션 출력이 아니다.')

    # 30
    g.page('WORKED ANSWERS / 02', '면접에서 물을 수 있는 다섯 질문', '답은 외우기보다 자신의 실험과 연결해 30-60초 안에 설명한다.', 'SELF-CHECK')
    g.head('6. 왜 플라즈마 밀도를 직접 입력하지 않았나요?')
    g.text('레시피 전력·압력·형상에서 수지를 풀어 나오는 상태로 두었기 때문이다. 전자밀도와 전력을 독립 입력으로 동시에 고정하면 수지가 충돌할 수 있다. 현재 모델은 정상 평균을 계산하며 점화 과정을 계산하지 않는다.')
    g.head('7. ALD 막이 더 두꺼워졌는데 왜 이상인가요?')
    g.text('두께 증가가 목표 범위 밖이고 깊은 곳 피복성이 나빠질 수 있다. 배기 이상 예에서는 A/B 잔류가 겹쳐 두 상태 표면 전환이 반복된다. 실제 불순물이나 CVD 성분을 측정한 것이 아니므로 그 부분은 추가 데이터가 필요하다.')
    g.head('8. 선택비가 좋아졌으니 RF 고장 조건이 더 좋지 않나요?')
    g.text('RF 이상에서 선택비는 17.3965로 높지만 깊이는 25.7830 nm로 부족하다. 선택비 하나가 다른 규격 미달을 상쇄하지 않는다. 공정 목표와 시간·마스크·균일도를 동시에 평가해야 한다.')
    g.head('9. 테스트가 통과했는데 왜 장비 정확도는 미검증인가요?')
    g.text('테스트는 정의한 식·수지·극한조건·입출력의 구현을 확인한다. 실제 재료의 계수와 장비가 같은 가정을 따르는지는 별도 문제다. 독립 실험의 동일 조건을 비교해야 물리 정확도를 평가할 수 있다.')
    g.head('10. 이 프로젝트가 PSE 역량과 어떻게 연결되나요?')
    g.text('목표를 규격으로 바꾸고, 이상을 관측해 경쟁 가설을 세우고, 구분 실험과 조치의 부작용을 설명하는 연습이다. Applied의 공개 PSE 설명에 나오는 가설 실험·DOE·데이터 분석·원인 분석과 연결된다. 실제 고객 현장 문제를 해결한 경력이라고 표현하지 않는다. [R4]')
    g.box('스스로 채점하는 기준', '용어만 말하면 0점, 수식/인과 경로를 설명하면 1점, 자기 실행 수치와 비교 기준을 제시하면 2점, 미검증·대안 가설·다음 확인까지 말하면 3점. 이는 본 교재의 연습 기준이다.')

    # 31
    g.page('PORTFOLIO / DELIVERABLE', '끝내야 할 것은 도구 다음의 실험', '시뮬레이터 제작은 출발점. 지원서에는 본인이 이해하고 수행한 분석을 담는다.', 'NEXT STEP')
    g.table(['프로젝트', '필수 결과물', '확장하면 좋은 검증'], [
        ['ALD 배기/공급', '기준-이상-보상 3조건, 분압·두께 분포, 5항목 평가', '주입 포화 곡선·형상 민감도·격자 확인'],
        ['Etch RF/바이어스', '4조건 깊이·마스크·선택비 비교, 원인 후보와 구분 실험', '같은 깊이 기준 비교·계수 민감도'],
        ['공통 설명', '실행 설정·모델 버전·코드·실험 노트·한계', '독립 문헌/측정 데이터와 비교 계획'],
    ], [119, 228, CW - 347], size=9.4)
    g.head('5분 발표 구성')
    g.text('30초: 왜 이 공정 문제를 골랐는가. 60초: 모델의 입력·상태·출력·가정. 90초: 기준과 이상 사례, 가설과 확인. 60초: 조치의 개선 효과와 부작용. 60초: 본인 기여, AI 지원, 실제 장비 적용 전 남은 검증.')
    g.box('직접 수행한 뒤 채울 지원서 문장', '“ALD/Etch 공정 원리를 이해하기 위해 Python 축약 모델을 검토하고 실험 환경을 구성했습니다. [본인이 설정한 문제]에서 [경쟁 가설]을 비교해 [실행 결과]를 확인했습니다. [조치]는 [지표]를 회복했지만 [비용/한계]가 남았고, 실제 적용을 위해 [추가 검증]이 필요함을 정리했습니다.”')
    g.head('과장하지 않는 표현')
    g.bullets(['“TCAD를 대체했다” 대신 계산한 물리와 누락 물리를 정확히 적는다.', '“장비 고장을 해결했다” 대신 주입한 모델 이상과 보상/복구를 구분한다.', '“직접 전부 개발했다”보다 본인이 설계·검토·해석한 범위와 AI 구현 지원을 구체적으로 적는다.'])
    g.text('오늘 밤 할 일: 기준 실행 1개를 저장하고, 수식·원리에서 출력 하나의 계산 경로를 설명한다. 다음에는 같은 규격으로 이상과 보상을 비교해 28쪽 노트 한 장을 채운다. 그 기록부터 본인의 포트폴리오가 된다.', size=10.5, leading=17, color=TEAL, bold=True)
    g.source('PSE 업무 연결 근거 [R4]. 제시한 프로젝트와 발표 형식은 개인 포트폴리오용 제안이다.')

    # 32
    g.page('REFERENCE / TRACEABILITY', '출처와 코드로 돌아가는 길', '열람·재실행 기준일 2026-09-30. 링크는 클릭 가능하며 채용 공고는 변경될 수 있다.', 'REFERENCE')
    refs = [
        ('R1', 'ASML, How microchips are made', 'https://www.asml.com/en/technology/all-about-microchips/how-microchips-are-made', '층별 제조 흐름·노광·계측 피드백의 개요.'),
        ('R2', 'Ylilammi, Ylivaara & Puurunen (2018), JAP 123, 205301', 'https://doi.org/10.1063/1.5028178', '수송-흡착 결합 ALD 모델 배경. 현재 교재는 저장소 식을 설명한다. 논문 전체를 재현하지 않는다.'),
        ('R3', 'Sungjin Kim (2006), UCB/EECS-2006-56', 'https://www2.eecs.berkeley.edu/Pubs/TechRpts/2006/EECS-2006-56.html', 'Ar 반응 계수 배경. 자세한 계수·손실식 출처는 ETCH_MODEL.md에 분리 기록.'),
        ('R4', 'Applied Materials, Process Support Engineer - Etch, R2619048', 'https://jobs.appliedmaterials.com/job/hillsboro/process-support-engineer-etch/95/94623970896', 'Hillsboro 경력 공고의 업무 설명 참고. AMK 신입 공고 자격요건으로 전용하지 않음.'),
        ('R5', 'NIST/SEMATECH, What is Process Capability?', 'https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm', 'C_p/C_pk 정의·안정성·분포·불확실성의 전제.'),
        ('R6', 'KLA, Chip Manufacturing', 'https://www.kla.com/products/chip-manufacturing', '검사·리뷰·계측·공정 관리의 연결.'),
        ('R7', 'ASML, The Rayleigh criterion for resolution', 'https://www.asml.com/en/technology/lithography-principles/rayleigh-criterion', 'CD=k₁λ/NA의 변수와 해상도 방향성.'),
    ]
    for key, title, url, desc in refs:
        g.text(f'<b>[{key}] <link href="{url}" color="#007F86">{escape(title)}</link></b><br/>{desc}', size=8.5, leading=12.8, gap=8)
    g.head('현재 구현의 1차 근거')
    g.text('[C1] sim_app/models/ald.py · docs/ALD_MODEL.md<br/>[C2] sim_app/models/etch.py · docs/ETCH_MODEL.md<br/>[C3] sim_app/frontend/src/assessment.ts · docs/PROCESS_ASSESSMENT_KR.md<br/>[C4] sim_app/run_reference_cases.py · 실행 ID는 13/14/21쪽<br/>[C5] docs/PROCESS_STUDIO_KR.md · sim_app/service.py<br/>[C6] sim_app/tests/test_ald.py · test_etch.py · test_server.py', size=8.5, leading=13.4, gap=10)
    g.text('<link href="https://github.com/TRX1200/pse-process-recovery-lab" color="#007F86"><b>공개 저장소</b></link> · <link href="https://trx1200.github.io/pse-process-recovery-lab/" color="#007F86"><b>공개 시뮬레이터</b></link><br/>재현: python sim_app/run_reference_cases.py --out outputs/study_reference<br/>PDF 재생성: python docs/study/build_study_pdf.py', size=8.7, leading=13.5, gap=10)
    g.box('마지막 체크', '내가 이해한 식 3개, 내가 실행한 비교 2개, 반례 1개, 남은 검증 1개를 설명할 수 있는가? 실제 계측이 없는 결과에는 “모델 내”라는 범위를 남긴다.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font-dir', type=Path, default=Path('C:/Windows/Fonts'))
    parser.add_argument('--output', type=Path, default=ROOT / 'output/pdf/Process_Studio_Semiconductor_Study_KR.pdf')
    args = parser.parse_args()
    pdfmetrics.registerFont(TTFont('KR', str(args.font_dir / 'malgun.ttf')))
    pdfmetrics.registerFont(TTFont('KRBold', str(args.font_dir / 'malgunbd.ttf')))
    pdfmetrics.registerFont(TTFont('MathSymbols', str(args.font_dir / 'arial.ttf')))
    pdfmetrics.registerFontFamily('KR', normal='KR', bold='KRBold', italic='KR', boldItalic='KRBold')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build(args.output)

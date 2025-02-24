from collections import OrderedDict
from copy import deepcopy
from typing import List

from pad.raw.skills.active_skill_info import ASConditional, PartWithTextAndCount
from pad.raw.skills.ja.skill_common import JaBaseTextConverter, TRANSLATION_NEEDED, minmax


def fmt_mult(x):
    return str(round(float(x), 2)).rstrip('0').rstrip('.')


ROW_INDEX = {
    0: '最上段',
    1: '上から2行目',
    2: '上から3行目',
    3: '下から2行目',
    4: '最下段',
}

COLUMN_INDEX = {
    0: '最左端',
    1: '左から2列目',
    2: '左から3列目',
    3: '右から3列目',
    4: '右から2列目',
    5: '最右端',
}


def half_to_full(n):
    o = ''
    c = '０１２３４５６７８９'
    for num in str(n):
        o += c[int(num)]
    return o


class JaASTextConverter(JaBaseTextConverter):
    def fmt_repeated(self, text, amount):
        return '{}ｘ{}回'.format(text, amount)

    def fmt_mass_atk(self, mass_attack):
        return '敵全体' if mass_attack else '敵1体'

    def fmt_duration(self, duration, max_duration=None):
        if max_duration and duration != max_duration:
            return '{}~{}ターンの間、'.format(duration, max_duration)
        else:
            return '{}ターンの間、'.format(duration)

    def attr_nuke_convert(self, act):
        return '{}に攻撃力ｘ{}倍の{}属性攻撃'.format(
            self.fmt_mass_atk(act.mass_attack), fmt_mult(act.multiplier), self.ATTRIBUTES[int(act.attribute)])

    def fixed_attr_nuke_convert(self, act):
        return '{}に{}の{}属性攻撃'.format(
            self.fmt_mass_atk(act.mass_attack), self.big_number(act.damage), self.ATTRIBUTES[int(act.attribute)])

    def self_att_nuke_convert(self, act):
        return '{}に攻撃力ｘ{}倍攻撃'.format(self.fmt_mass_atk(act.mass_attack), fmt_mult(act.multiplier))

    def shield_convert(self, act):
        return self.fmt_duration(act.duration) + self.fmt_reduct_text(act.shield)

    def elemental_shield_convert(self, act):
        if act.shield == 1:
            return '{}ターンの間、{}属性の攻撃を無効化'.format(
                act.duration, self.attributes_to_str([int(act.attribute)]))
        else:
            return '{}ターンの間、{}属性のダメージを{}％減少'.format(
                act.duration, self.attributes_to_str([int(act.attribute)]), fmt_mult(act.shield * 100))

    def drain_attack_convert(self, act):
        skill_text = '{}に攻撃力ｘ{}倍で攻撃し、ダメージ'.format(self.fmt_mass_atk(act.mass_attack), fmt_mult(act.atk_multiplier))
        if act.recover_multiplier == 1:
            skill_text += '分のHP回復'
        else:
            skill_text += '{}％分のHP回復'.format(fmt_mult(act.recover_multiplier * 100))
        return skill_text

    def poison_convert(self, act):
        return '敵全体を毒にする（攻撃力ｘ{}倍）'.format(fmt_mult(act.multiplier))

    def ctw_convert(self, act):
        return '{}秒間、時を止めてドロップを動かせる'.format(act.duration)

    def gravity_convert(self, act):
        return '敵の現HPの{}％分のダメージ'.format(fmt_mult(act.percentage_hp * 100))

    def heal_active_convert(self, act):
        hp = getattr(act, 'hp', 0)
        rcv_mult = getattr(act, 'rcv_multiplier_as_hp', 0)
        php = getattr(act, 'percentage_max_hp', 0)
        trcv_mult = getattr(act, 'team_rcv_multiplier_as_hp', 0)
        unbind = getattr(act, 'card_bind', 0)
        awoken_unbind = getattr(act, 'awoken_bind', 0)

        skill_text = ('HPを{}回復'.format(self.big_number(hp)) if hp != 0 else
                      ('回復力ｘ{}倍のHPを回復'.format(fmt_mult(rcv_mult)) if rcv_mult != 0 else
                       ('HPを全回復' if php == 1 else
                        ('最大HP{}％分回復'.format(fmt_mult(php * 100)) if php > 0 else
                         ('チームの総回復力ｘ{}倍のHPを回復'.format(fmt_mult(trcv_mult)) if trcv_mult > 0 else
                          (''))))))

        if unbind or awoken_unbind:
            if skill_text:
                skill_text += '。'
            skill_text += ('バインドと覚醒無効を全回復' if unbind >= 9999 and awoken_unbind else
                           ('バインドと覚醒無効を{}ターン回復'.format(awoken_unbind) if unbind and awoken_unbind else
                            ('バインドを全回復' if unbind >= 9999 else
                             ('バインドを{}ターン回復'.format(unbind) if unbind else
                              ('覚醒無効を全回復' if awoken_unbind >= 9999 else
                               ('覚醒無効を{}ターン回復'.format(awoken_unbind)))))))
        return skill_text

    def delay_convert(self, act):
        return '敵の行動を{}ターン遅らせる'.format(act.turns)

    def defense_reduction_convert(self, act):
        return '{}ターンの間、敵の防御力が{}％下がる'.format(act.duration, fmt_mult(act.shield * 100))

    def double_orb_convert(self, act):
        if len(act.to_attr) == 1:
            skill_text = '{}と{}ドロップを{}ドロップに変化'.format(
                self.ATTRIBUTES[int(act.from_attr[0])],
                self.ATTRIBUTES[int(act.from_attr[1])],
                self.ATTRIBUTES[int(act.to_attr[0])])
        else:
            skill_text = '{}ドロップを{}ドロップに、{}ドロップを{}ドロップに変化'.format(
                self.ATTRIBUTES[int(act.from_attr[0])],
                self.ATTRIBUTES[int(act.to_attr[0])],
                self.ATTRIBUTES[int(act.from_attr[1])],
                self.ATTRIBUTES[int(act.to_attr[1])])

        return skill_text

    def damage_to_att_enemy_convert(self, act):
        return '{}属性の敵に{}属性の{}ダメージ'.format(
            self.ATTRIBUTES[int(act.enemy_attribute)],
            self.ATTRIBUTES[int(act.attack_attribute)],
            act.damage)

    def rcv_boost_convert(self, act):
        return '{}ターンの間、回復力が{}倍'.format(act.duration, fmt_mult(act.multiplier))

    def attribute_attack_boost_convert(self, act):
        skill_text = ''
        if act.rcv_boost:
            skill_text += self.rcv_boost_convert(act) + '。'
        skill_text += self.fmt_duration(act.duration) + self.fmt_stats_type_attr_bonus(act, atk=act.multiplier)
        return skill_text

    def mass_attack_convert(self, act):
        return '{}ターンの間、攻撃が全体攻撃になる'.format(act.duration)

    def enhance_convert(self, act):
        for_attr = act.orbs
        skill_text = ''

        if for_attr:
            if not len(for_attr) == 6:
                skill_text = '{}ドロップを強化'.format(self.attributes_to_str(for_attr))
            else:
                skill_text = '全ドロップを強化'
        return skill_text

    def lock_convert(self, act):
        for_attr = act.orbs
        amount_text = '全' if act.count >= 42 else 'ランダムで{}個'.format(act.count)
        color_text = '' if len(for_attr) == 10 else self.attributes_to_str(for_attr)
        return '{}{}ドロップをロック'.format(amount_text, color_text)

    def laser_convert(self, act):
        return '{}に{}の固定ダメージ'.format(
            self.fmt_mass_atk(act.mass_attack), self.big_number(act.damage))

    def no_skyfall_convert(self, act):
        return '{}ターンの間、落ちコンしなくなる'.format(act.duration)

    def enhance_skyfall_convert(self, act):
        return '{}ターンの間、強化ドロップを{}％の確率で落ちてくる'.format(
            act.duration, fmt_mult(act.percentage_increase * 100))

    def auto_heal_convert(self, act):
        skill_text = ''
        unbind = act.card_bind
        awoken_unbind = act.awoken_bind
        if act.duration:
            skill_text += '{}ターンの間、最大HPの{}％分回復'.format(
                act.duration, fmt_mult(act.percentage_max_hp * 100))
        if unbind or awoken_unbind:
            if skill_text:
                skill_text += '。'
            skill_text += ('バインドと覚醒無効を全回復' if unbind >= 9999 and awoken_unbind else
                           ('バインドと覚醒無効を{}ターン回復'.format(awoken_unbind) if unbind and awoken_unbind else
                            ('バインドを全回復' if unbind >= 9999 else
                             ('バインドを{}ターン回復'.format(unbind) if unbind else
                              ('覚醒無効を全回復' if awoken_unbind >= 9999 else
                               ('覚醒無効を{}ターン回復'.format(awoken_unbind)))))))
        return skill_text

    def absorb_mechanic_void_convert(self, act):
        if act.attribute_absorb and act.damage_absorb:
            return self.fmt_duration(act.duration) + 'ダメージ吸収と属性吸収を無効化する'
        elif act.attribute_absorb and not act.damage_absorb:
            return self.fmt_duration(act.duration) + '属性吸収を無効化する'
        elif not act.attribute_absorb and act.damage_absorb:
            return self.fmt_duration(act.duration) + 'ダメージ吸収を無効化する'
        else:
            return ''

    def void_mechanic_convert(self, act):
        return self.fmt_duration(act.duration) + 'ダメージ無効を貫通する'

    def true_gravity_convert(self, act):
        return '敵の最大HPの{}％分のダメージ'.format(fmt_mult(act.percentage_max_hp * 100))

    def extra_combo_convert(self, act):
        return self.fmt_duration(act.duration) + '{}コンボ加算される'.format(act.combos)

    def awakening_heal_convert(self, act):
        skill_text = 'チーム内の'
        awakens = [f"{{{{ awoskills.id{a}|default('???') }}}}" for a in act.awakenings if a]
        skill_text += self.concat_list_and(awakens)
        skill_text += 'の覚醒数1つにつき回復力ｘ{}倍をHP回復'.format(act.amount_per)
        return skill_text

    def awakening_attack_boost_convert(self, act):
        skill_text = self.fmt_duration(act.duration) + 'チーム内の'
        awakens = [f"{{{{ awoskills.id{a}|default('???') }}}}" for a in act.awakenings if a]
        skill_text += self.concat_list_and(awakens)
        skill_text += 'の覚醒数1つにつき攻撃力が{}％上がる'.format(fmt_mult(act.amount_per * 100))
        return skill_text

    def awakening_shield_convert(self, act):
        skill_text = self.fmt_duration(act.duration) + 'チーム内の'
        awakens = [f"{{{{ awoskills.id{a}|default('???') }}}}" for a in act.awakenings if a]
        skill_text += self.concat_list_and(awakens)
        skill_text += 'の覚醒数1つにつき受けるダメージを{}％減少'.format(fmt_mult(act.amount_per * 100))
        return skill_text

    def awakening_stat_boost_convert(self, act):
        # TODO: Write this better
        skill_text = ""
        if act.atk_per:
            skill_text = self.fmt_duration(act.duration) + 'チーム内の'
            awakens = self.concat_list_and(f"{{{{ awoskills.id{a}|default('???') }}}}"
                                           for a in act.awakenings if a)
            skill_text += f'の覚醒数1つにつき攻撃力が{fmt_mult(act.atk_per * 100)}％上がる'
            if act.rcv_per:
                skill_text += '。'
        if act.rcv_per:
            skill_text += self.fmt_duration(act.duration) + 'チーム内の'
            awakens = self.concat_list_and(f"{{{{ awoskills.id{a}|default('???') }}}}"
                                           for a in act.awakenings if a)
            skill_text += f'の覚醒数1つにつき回復力が{fmt_mult(act.rcv_per * 100)}％上がる'
        return skill_text

    def change_enemies_attribute_convert(self, act):
        skill_text = ""
        if act.turns is not None:
            skill_text += self.fmt_duration(act.turns)
        return skill_text + '敵全体が{}属性に変化'.format(self.ATTRIBUTES[act.attribute])

    def haste_convert(self, act):
        return '自分以外の味方スキルが{}ターンの溜まる'.format(minmax(act.turns, act.max_turns))

    def hp_boost(self, act):
        return "{}ターンの間、最大HPが{}倍".format(act.duration, fmt_mult(act.hp))

    def random_orb_change_convert(self, act):
        from_attr = act.from_attr
        to_attr = act.to_attr
        if from_attr == self.ALL_ATTRS:
            skill_text = '全'
        else:
            skill_text = self.attributes_to_str(from_attr)
        skill_text += 'ドロップを{}ドロップに変化'.format(self.attributes_to_str(to_attr))
        return skill_text

    def attack_attr_x_team_atk_convert(self, act):
        return '{}にチームの{}属性の総攻撃力ｘ{}倍の{}属性攻撃'.format(
            self.fmt_mass_atk(act.mass_attack),
            self.attributes_to_str(act.team_attributes),
            fmt_mult(act.multiplier),
            self.ATTRIBUTES[act.attack_attribute])

    def spawn_orb_convert(self, act):
        to_orbs = self.attributes_to_str(act.orbs)
        excl_orbs = self.attributes_to_str(set(act.excluding_orbs) - set(act.orbs))
        if act.orbs != act.excluding_orbs and act.excluding_orbs != []:
            if len(act.orbs) > 1:
                s_text = '{}以外ランダムで{}を{}個ずつ生成'
            else:
                s_text = '{}以外{}ドロップを{}個生成'
            return s_text.format(excl_orbs, to_orbs, act.amount)
        else:
            if len(act.orbs) > 1:
                s_text = 'ランダムで{}を{}個ずつ生成'
            else:
                s_text = '{}ドロップを{}個生成'
            return s_text.format(to_orbs, act.amount)

    def double_spawn_orb_convert(self, act):
        s_text = self.spawn_orb_convert(act) + "。"
        to_orbs = self.attributes_to_str(act.orbs2)
        excl_orbs = self.attributes_to_str(set(act.excluding_orbs2) - set(act.orbs2))
        if act.orbs2 != act.excluding_orbs2 and act.excluding_orbs2 != []:
            if len(act.orbs2) > 1:
                s_text += '{}以外ランダムで{}を{}個ずつ生成'
            else:
                s_text += '{}以外{}ドロップを{}個生成'
            return s_text.format(excl_orbs, to_orbs, act.amount2)
        else:
            if len(act.orbs2) > 1:
                s_text += 'ランダムで{}を{}個ずつ生成'
            else:
                s_text += '{}ドロップを{}個生成'
            return s_text.format(to_orbs, act.amount2)

    def move_time_buff_convert(self, act):
        s_text = self.fmt_duration(act.duration) + 'ドロップ操作時間が'
        if act.static == 0:
            return s_text + '{}倍'.format(fmt_mult(act.percentage))
        elif act.percentage == 0:
            return s_text + '{}秒に延長'.format(fmt_mult(act.static))
        raise ValueError()

    def row_change_convert(self, act):
        return self._line_change_convert(act.rows, ROW_INDEX)

    def column_change_convert(self, act):
        return self._line_change_convert(act.columns, COLUMN_INDEX)

    def _line_change_convert(self, lines, index):
        skill_text = []
        # TODO: simplify this
        lines = [(index[line.index], self.attributes_to_str(line.attrs)) for line in lines]
        skip = 0
        for c, line in enumerate(lines):
            if skip:
                skip -= 1
                continue
            elif c == len(lines) - 1 or lines[c + 1][1] != line[1]:
                skill_text.append('{}を{}に'.format(*line))
            else:
                while c + skip < len(lines) and lines[c + skip][1] == line[1]:
                    skip += 1
                formatted = 'と'.join(map(lambda x: x[0], lines[c:c + skip]))
                skill_text.append("{}を{}に".format(formatted, line[1]))
                skip -= 1
        output = '、'.join(skill_text)
        if output:
            output = output[:-1] + 'ドロップに変化'
        return output

    def change_skyfall_convert(self, act):
        skill_text = self.fmt_duration(act.duration, act.max_duration)
        rate = fmt_mult(act.percentage * 100)

        if rate == '100':
            skill_text += '{}ドロップのみ落ちてくる'.format(self.attributes_to_str(act.orbs))
        else:
            if all(map(lambda x: x in range(6), act.orbs)):
                skill_text += '{}ドロップが{}％落ちやすくなる'.format(self.attributes_to_str(act.orbs), rate)
            else:
                skill_text += '{}が{}％の確率で落ちてくる'.format(self.attributes_to_str(act.orbs), rate)
        return skill_text

    def no_orb_skyfall_convert(self, act):
        skill_text = self.fmt_duration(act.duration)
        skill_text += 'no {} orbs will appear'.format(self.concat_list_and(self.ATTRIBUTES[i] for i in act.orbs))
        return skill_text

    def random_nuke_convert(self, act):
        return '{}に攻撃力ｘ{}倍の{}属性攻撃'.format(
            self.fmt_mass_atk(act.mass_attack),
            minmax(fmt_mult(act.minimum_multiplier), fmt_mult(act.maximum_multiplier)),
            self.ATTRIBUTES[act.attribute])

    def counterattack_convert(self, act):
        return '{}ターンの間、受けたダメージｘ{}倍の{}属性反撃'.format(
            act.duration, fmt_mult(act.multiplier), self.ATTRIBUTES[act.attribute])

    def board_change_convert(self, act):
        return '全ドロップを{}ドロップに変化'.format(self.attributes_to_str(act.to_attr))

    def suicide_random_nuke_convert(self, act):
        return self.suicide_convert(act) + '。' + self.random_nuke_convert(act)

    def suicide_nuke_convert(self, act):
        skill_text = self.suicide_convert(act) + '。'
        skill_text += '{}に{}属性の{}ダメージ'.format(
            self.fmt_mass_atk(act.mass_attack), self.ATTRIBUTES[act.attribute], self.big_number(act.damage))
        return skill_text

    def suicide_convert(self, act):
        if act.hp_remaining == 0:
            return 'HPが1になる'
        else:
            return 'HPが{}％減少'.format(fmt_mult((1 - act.hp_remaining) * 100))

    def type_attack_boost_convert(self, act):
        return '{}ターンの間、{}タイプの攻撃力が{}倍'.format(
            act.duration, self.typing_to_str(act.types), fmt_mult(act.multiplier))

    def grudge_strike_convert(self, act):
        return '残りHPが応じ{}に{}属性ダメージを与え（HP1のとき攻撃力ｘ{}倍、満タン{}倍）'.format(
            self.fmt_mass_atk(act.mass_attack),
            self.ATTRIBUTES[act.attribute],
            fmt_mult(act.low_multiplier),
            fmt_mult(act.high_multiplier))

    def drain_attr_attack_convert(self, act):
        skill_text = '{}に攻撃力ｘ{}倍の{}属性攻撃し、ダメージ'.format(
            self.fmt_mass_atk(act.mass_attack), fmt_mult(act.atk_multiplier), self.ATTRIBUTES[int(act.attribute)])

        if act.recover_multiplier == 1:
            skill_text += '分のHP回復'
        else:
            skill_text += 'の{}％分のHP回復'.format(fmt_mult(act.recover_multiplier * 100))
        return skill_text

    def attribute_change_convert(self, act):
        return '{}ターンの間、自分の属性が{}属性に変化'.format(
            act.duration, self.ATTRIBUTES[act.attribute])

    def multi_hit_laser_convert(self, act):
        return '{}に{}ダメージ'.format(self.fmt_mass_atk(act.mass_attack), act.damage)

    def hp_nuke_convert(self, act):
        return "{}にチームの総HPｘ{}倍の{}属性攻撃".format(
            self.fmt_mass_atk(act.mass_attack),
            fmt_mult(act.multiplier),
            self.ATTRIBUTES[act.attribute])

    def get_shape(self, act) -> List[str]:
        board = deepcopy(act.pos_map)
        orb_count = sum(map(len, board))

        output = []
        shapes = []

        shape = "<UNDEFINED>"
        if orb_count == 4:
            if len(board[0]) == len(board[4]) == 2:
                shapes.append('盤面4隅に')

        if not (orb_count % 5):
            for x in range(1, len(board) - 1):  # Check for cross
                if len(board[x]) == 3 and len(board[x - 1]) == len(board[x + 1]) == 1:  # Check for cross
                    row_pos = x
                    col_pos = board[x][1]
                    shape = '十字形'
                    result = (shape, row_pos, col_pos)
                    output.append(result)
                    del board[x][1]
            for x in range(0, len(board)):  # Check for L
                if len(board[x]) == 3:
                    row_pos = x
                    if x < 2:
                        col_pos = board[x + 1][0]
                        del board[x + 1][0]
                    elif x > 2:
                        col_pos = board[x - 1][0]
                        del board[x - 1][0]
                    elif len(board[x + 1]) > 0:
                        col_pos = board[x + 1][0]
                        del board[x + 1][0]
                    else:
                        col_pos = board[x - 1][0]
                        del board[x - 1][0]

                    shape = 'L字形'
                    result = (shape, row_pos, col_pos)
                    output.append(result)

        if not (orb_count % 9):
            # Check for square
            for x in range(1, len(board) - 1):
                if len(board[x]) == len(board[x - 1]) == len(board[x + 1]) == 3:
                    row_pos = x
                    col_pos = board[x][1]
                    shape = '正方形'
                    result = (shape, row_pos, col_pos)
                    output.append(result)
                    del board[x][1]
        if orb_count == 18:
            if len(board[0]) == len(board[4]) == len(board[1]) + len(board[2]) + len(board[3]) == 6:
                shapes.append('盤面外周を')

        if board == [[3, 4, 5], [3, 5], [5], [5], []]:
            shapes.append('7の形に')

        if board == [[0, 1, 2], [0, 1, 2], [], [], []]:
            shapes.append('Create a 3x2 rectangle in the upper left corner')

        if board == [[], [1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4], []]:
            shapes.append('盤面中央を')

        if board == [[4, 5], [3, 4], [2, 3], [1, 2], [0, 1]]:
            shapes.append('盤面上に斜めに')

        if board == [[2, 3, 4], [1, 4, 5], [5], [1, 4, 5], [2, 3, 4]]:
            shapes.append('三日月状に')
 
        if board == [[0, 1, 2, 3, 4], [3], [2], [1], [0, 1, 2, 3, 4]]:
            shapes.append('盤面上にZ字型に')

        for shape, row_pos, col_pos in output:
            shapes.append('{}と{}の中心に{}の'.format(
                ROW_INDEX[row_pos],
                COLUMN_INDEX[col_pos],
                shape,
            ))

        if not shapes and orb_count:
            for idx, row in enumerate(board):
                if len(row) == 6:
                    shapes.append(ROW_INDEX[idx])
            for idx in range(6):
                if sum(row.count(idx) for row in board) == 5:
                    shapes.append(COLUMN_INDEX[idx])

        return shapes

    def fixed_pos_convert(self, act):
        skill_text = '。'.join(
            f'{shape}{self.ATTRIBUTES[act.attribute]}ドロップを1つ生成'
            for shape in
            self.get_shape(act)
        )

        return skill_text

    def match_disable_convert(self, act):
        return '消せないドロップ状態を{}ターン回復'.format(act.duration)

    def board_refresh(self, act):
        return 'ランダムでドロップを入れ替える'

    def leader_swap(self, act):
        return 'リーダーと入れ替わる；もう一度使うとサブに戻る'

    def unlock_all_orbs(self, act):
        return '全ドロップのロック状態を解除'

    def unlock_board_path_toragon(self, act):
        return '全ドロップのロック状態を解除し、火、水、木と光ドロップに変化。3コンボ分のルートを表示。'

    def random_skill(self, act):
        random_skills_text = []
        for idx, s in enumerate(act.child_skills, 1):
            random_skills_text.append('{}、{}'.format(half_to_full(idx), s.templated_text(self)))
        return '下からスキルをランダムて発動：{}'.format("；".join(random_skills_text))

    def change_monster(self, act):
        return f"[{next(iter(act.transform_ids))}]に変身する"

    def random_change_monster(self, act):
        # TODO: Add probabilities
        return "ランダムで変身：{}".format(
            self.concat_list_and((f'[{id}]' for id in act.transform_ids), conj='か')
        )

    def skyfall_lock(self, act):
        attrs = self.attributes_to_str(act.orbs) if act.orbs else ''
        return "{}ターンの間、{}ドロップがロック状態で落ちてくる".format(act.duration, attrs)

    def spawn_spinner(self, act):
        if act.random_count:
            return '{}ターンの間、ランダムで{}箇所のマスがが{}秒毎に変化する' \
                .format(act.turns, act.random_count, act.speed)
        else:
            shapes = self.get_shape(act)
            position = '、'.join(shapes)
            return '{}ターンの間、{}にルーレットを生成({}秒毎に変化する)' \
                .format(act.turns, position, act.speed)

    def ally_active_disable(self, turns: int):
        return '{}ターンの間、スキル使用不可。'.format(turns)

    def ally_active_delay(self, turns: int):
        return '味方スキルが{}ターン減少。'.format(turns)

    def create_unmatchable(self, act):
        skill_text = self.fmt_duration(act.duration) + self.concat_list_and(self.ATTRIBUTES[i] for i in act.orbs)
        skill_text += 'ドロップが消せなくなる。'
        return skill_text

    def conditional_hp_thresh(self, act):
        if act.lower_limit == 0:
            return f"HP {act.upper_limit}%以下："
        if act.upper_limit == 100:
            return f"HP {act.lower_limit}%以上："
        return f"HP {act.lower_limit}%～{act.upper_limit}%の場合："

    def nail_orb_skyfall(self, act):
        return f'{self.fmt_duration(act.duration)}釘ドロップが{fmt_mult(act.chance * 100)}％落ちやすくなる'

    def lead_swap_sub(self, act):
        return f'リーダーと左から{act.sub_slot}番のサブを入れ替える'

    def composition_buff(self, act):
        if act.attributes and act.types:
            return ""
        skill_text = self.fmt_duration(act.duration)
        if act.attributes:
            return skill_text + f"チーム内の{self.fmt_multi_attr(act.attributes)}一体につき" \
                                f"攻撃力が{int(act.atk_boost*100)}%と回復力が{int(act.rcv_boost*100)}%上がる"
        else:
            return skill_text + f"チーム内の{self.typing_to_str(act.types, '、')}一つにつき" \
                                f"攻撃力が{int(act.atk_boost*100)}%と回復力が{int(act.rcv_boost*100)}%上がる"

    def team_target_stat_change(self, act):
        if act.target == 1:
            return self.fmt_duration(act.duration) + f"自分の攻撃力を{fmt_mult(act.atk_mult)}倍"
        elif act.target == 2:
            return self.fmt_duration(act.duration) + f"リーダーの攻撃力を{fmt_mult(act.atk_mult)}倍"
        elif act.target == 4:
            return self.fmt_duration(act.duration) + f"助っ人の攻撃力を{fmt_mult(act.atk_mult)}倍"
        elif act.target == 8:
            return self.fmt_duration(act.duration) + f"サブ4体の攻撃力を{fmt_mult(act.atk_mult)}倍"
        elif act.target == 15:
            return self.fmt_duration(act.duration) + f"全員の攻撃力を{fmt_mult(act.atk_mult)}倍"
        else:
            return self.fmt_duration(act.duration) + f"???の攻撃力を{fmt_mult(act.atk_mult)}倍"

    def evolving_active(self, act):
        skill_text = "スキル使うと、次の階段に変化。最終階段のスキル使うと、最初のスキル戻る："
        skill_text += '；'.join(f"{half_to_full(c)}、{skill.templated_text(self)}"
                              for c, skill in enumerate(act.child_skills, 1))
        return skill_text

    def looping_evolving_active(self, act):
        skill_text = "スキル使うと、次の階段に変化："
        skill_text += '；'.join(f"{half_to_full(c)}、{skill.templated_text(self)}"
                              for c, skill in enumerate(act.child_skills, 1))
        return skill_text

    def conditional_floor_thresh(self, act, context):
        if act.lower_limit == 0:
            return f"バトル{act.upper_limit}以前："
        if act.upper_limit == 9999:
            return f"バトル{act.lower_limit}以降："
        return f"バトル{act.lower_limit}～{act.upper_limit}："

    def multi_part_active(self, act):
        text_to_item = OrderedDict()
        for p in act.parts:
            p_text = p.text(self)
            if p_text in text_to_item:
                text_to_item[p_text].repeat += 1
            else:
                text_to_item[p_text] = PartWithTextAndCount(p, p_text)

        return self.combine_skills_text(list(text_to_item.values()))

    def combine_skills_text(self, skills: List[PartWithTextAndCount]):
        skill_text = ""
        for c, skillpart in enumerate(skills):
            skill_text += skillpart.templated_text(self)
            if c != len(skills) - 1 and not isinstance(skillpart.act, ASConditional):
                skill_text += '。'
        return skill_text

    def cloud(self, act):
        if act.cloud_width == 6 and act.cloud_height == 1:
            shape = '横1列'
        elif act.cloud_width == 1 and act.cloud_height == 5:
            shape = '縦1列'
        elif act.cloud_width == act.cloud_height:
            shape = '{}×{}マスの正方形'.format(act.cloud_width, act.cloud_height)
        else:
            shape = '{}×{}マスの長方形'.format(act.cloud_width, act.cloud_height)
        pos = []
        if act.origin_x is not None and shape != '横1列':
            pos.append('左から{}列目'.format(act.origin_x))
        if act.origin_y is not None and shape != '縦1列':
            pos.append('上から{}列目'.format(act.origin_y))
        if len(pos) == 0:
            pos.append('ランダムで')
        return '{}ターンの間、{}の{}を雲で隠す'.format(act.duration, '、'.join(pos), shape)

    def damage_cap_boost(self, act):
        return "{}ターンの間、自分のダメージ上限値が{}億になる".format(act.duration, act.damage_cap)

    def inflict_es(self, act):
        if act.selector_type == 2:
            skill_text = self.concat_list_and(f'{p}位' for p in act.players) + 'のプレイヤー'
        elif act.selector_type == 3:
            skill_text = "自分より上位のプレイヤーの皆様へ"
        else:
            skill_text = "To some other players, "
        return skill_text + "に意地悪をする"

    def orb_seal(self, act):
        return '{}ターンの間、左から{}列目のドロップが操作不可' \
            .format(act.duration, act.column)

    def tape(self, act):
        return TRANSLATION_NEEDED

    def changeto7x6board(self, act):
        return self.fmt_duration(act.duration) + '盤面を7×6マスにする。'


__all__ = ['JaASTextConverter']

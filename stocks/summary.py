import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fact_ids: list[str]


def facts_for(table, target):
    facts = {}
    for symbol, row in table.iterrows():
        facts[f'{symbol}:daily'] = (
            f'{target}: {symbol} closed at {row.close:.2f} HUF, '
            f'daily price change {row.change_HUF:+.2f} HUF ({row.change_pct:+.2f}%), volume {int(row.volume):,} shares.')
        if symbol != 'BUX.BUD':
            facts[f'{symbol}:benchmark'] = (
                f'{symbol} daily return differs from BUX.BUD by {row.vs_BUX.BUD_pp:+.2f} percentage points.')
    return facts


def select_with_openai(facts, config):
    from openai import OpenAI
    if not config['OPENAI_API_KEY'] or not config['OPENAI_MODEL']:
        raise ValueError('Set OPENAI_API_KEY and OPENAI_MODEL.')
    prompt = (Path(__file__).resolve().parents[1] / 'prompts/daily_summary.txt').read_text(encoding='utf-8')
    client = OpenAI(api_key=config['OPENAI_API_KEY'], timeout=45, max_retries=2)
    response = client.responses.parse(
        model=config['OPENAI_MODEL'], store=False, max_output_tokens=2000,
        input=[{'role': 'system', 'content': prompt},
               {'role': 'user', 'content': json.dumps(facts, ensure_ascii=False)}],
        text_format=Selection,
    )
    if response.status != 'completed' or response.output_parsed is None:
        raise ValueError('The AI response is incomplete or refused.')
    return response.output_parsed.fact_ids


def validate_selection(ids, facts):
    if not ids or len(ids) > len(facts) or len(ids) != len(set(ids)):
        return ['Empty, oversized or duplicate AI selection.']
    if any(fact_id not in facts for fact_id in ids):
        return ['The AI referenced an unknown fact.']
    required = {k for k in facts if k.endswith(':daily')}
    if not required.issubset(ids):
        return ['Incomplete symbol or benchmark coverage.']
    return []


def render(ids, facts):
    errors = validate_selection(ids, facts)
    if errors:
        raise ValueError('; '.join(errors))
    return '\n\n'.join(facts[i] for i in ids)



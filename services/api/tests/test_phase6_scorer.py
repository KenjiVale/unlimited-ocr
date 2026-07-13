import pytest
from app.services.phase6_scoring import *

def test_identical(): assert calculate_cer("abc","abc").error_rate==0 and calculate_wer("a b","a b").error_rate==0
def test_char_sub(): assert calculate_cer("abc","axc").substitutions==1
def test_char_ins(): assert calculate_cer("abc","abxc").insertions==1
def test_char_del(): assert calculate_cer("abc","ac").deletions==1
def test_word_sub(): assert calculate_wer("a b","a c").substitutions==1
def test_whitespace(): assert normalize_content_relaxed("a  \n b")=="a b"
def test_punctuation(): assert calculate_cer("a.","a!").substitutions==1
def test_heading(): assert normalize_content_strict("# Hello")=="Hello"
def test_page_heading(): assert normalize_content_strict("# OCR Result\n## Page 1\nHi")=="Hi"
def test_table_separator(): assert "Item" in normalize_content_strict("| Item |\n|---|\n| Pen |")
def test_empty_ocr(): assert calculate_cer("abc","").deletions==3
def test_missing_page(): assert page_counts(["a","b"],["a"])[0].deletions==1
def test_extra_page(): assert page_counts(["a"],["a","b"])[0].insertions==1
def test_duplicate_page(): assert page_counts(["a"],["a","a"])[0].insertions==1
def test_reversed(): assert page_counts(["a","b"],["b","a"])[0].substitutions==2
def test_identical_pages(): assert page_counts(["a","b"],["a","b"])[0].error_rate==0
def test_different_pages(): assert page_counts(["a","b"],["a","c"])[0].substitutions==1
def test_collision(tmp_path):
 p=tmp_path/'x';p.write_text('x');
 with pytest.raises(ValueError):validate_paths(p,p)
def test_missing_ocr(tmp_path):
 t=tmp_path/'t';t.write_text('x');
 with pytest.raises(ValueError):validate_paths(tmp_path/'o',t)
def test_numeric_normalization(): assert normalize_content_relaxed('Rp 1,250')=='Rp 1,250'
def test_currency_required(): assert 'IDR' not in normalize_content_relaxed('138750')
def test_table_borders(): assert normalize_content_strict('|A|\n|---|\n|B|')=='|A|\n\n|B|'
def test_cell_omission(): assert calculate_wer('A B','A').deletions==1
def test_duplicate_record_key(): assert len({('a','primary',200),('a','primary',200)})==1

def test_parser_three_pages():
 pages=extract_ocr_pages_from_markdown('# OCR Result\n\n## Page 1\n\nFirst page.\n\n## Page 2\n\nSecond page.\n\n## Page 3\n\nThird page.')
 assert [p.page_number for p in pages]==[1,2,3] and pages[1].markdown=='Second page.'
def test_parser_preserves_markdown():
 p=extract_ocr_pages_from_markdown('## Page 1\n\n### Heading\n- one\n|A|B|\n|--|--|\n|x|y|\n\nText!')[0]
 assert '### Heading' in p.markdown and '- one' in p.markdown and '|x|y|' in p.markdown
def test_wrapper_ignored(): assert extract_ocr_pages_from_markdown('# OCR Result\n## Page 1\nHi')[0].markdown=='Hi'
def test_arbitrary_heading_not_split(): assert '## Summary' in extract_ocr_pages_from_markdown('## Page 1\nA\n## Summary\nB\n### Notes\nC')[0].markdown
def test_inline_marker_not_split(): assert len(extract_ocr_pages_from_markdown('## Page 1\nThe text says ## Page 2 inline.'))==1
def test_duplicate_page_rejected():
 with pytest.raises(DuplicateOCRPageNumber): extract_ocr_pages_from_markdown('## Page 1\nFirst\n## Page 1\nDuplicate')
def test_empty_page_rejected():
 with pytest.raises(OCRPageParseError): extract_ocr_pages_from_markdown('## Page 1\n\n## Page 2\nValid')
def test_no_marker_rejected():
 with pytest.raises(OCRPageParseError): extract_ocr_pages_from_markdown('## Summary\nOrdinary')
def test_missing_number_preserved(): assert [p.page_number for p in extract_ocr_pages_from_markdown('## Page 1\nOne\n## Page 3\nThree')]==[1,3]
def test_nonascending_rejected():
 with pytest.raises(OCRPageParseError,match='strictly ascending'): extract_ocr_pages_from_markdown('## Page 2\nTwo\n## Page 1\nOne')
def test_ground_truth_loader(tmp_path):
 p=tmp_path/'pages.json';p.write_text('{"document_id":"multi-page-test","pages":[{"page_number":1,"text":"First page"},{"page_number":2,"text":"Second page"}]}')
 assert [x.text for x in load_page_ground_truth(p)]==['First page','Second page']
def test_duplicate_ground_truth_rejected(tmp_path):
 p=tmp_path/'pages.json';p.write_text('{"document_id":"x","pages":[{"page_number":1,"text":"a"},{"page_number":1,"text":"b"}]}')
 with pytest.raises(ValueError): load_page_ground_truth(p)
def test_empty_ground_truth_rejected(tmp_path):
 p=tmp_path/'pages.json';p.write_text('{"document_id":"x","pages":[{"page_number":1,"text":" "}]}')
 with pytest.raises(ValueError): load_page_ground_truth(p)
def test_missing_ocr_loader_source(tmp_path):
 with pytest.raises(OCRPageParseError,match='missing'): load_multi_page_ocr(tmp_path/'missing.md')
def test_empty_ocr_loader_source(tmp_path):
 p=tmp_path/'empty.md';p.write_text(' ')
 with pytest.raises(OCRPageParseError,match='empty'): load_multi_page_ocr(p)


def test_one_page_aligned_scoring():
 result=score_page_aligned_document([OCRPage(1,'alpha')],[GroundTruthPage(1,'alpha')])
 assert result.raw_markdown.cer==0 and result.raw_markdown.wer==0


def test_three_page_aligned_scoring():
 result=score_page_aligned_document([OCRPage(1,'a'),OCRPage(2,'b'),OCRPage(3,'c')],[GroundTruthPage(1,'a'),GroundTruthPage(2,'b'),GroundTruthPage(3,'c')])
 assert [page.page_number for page in result.pages]==[1,2,3] and result.strict_content.cer==0


def test_weighted_character_aggregation():
 result=score_page_aligned_document([OCRPage(1,'abcd'),OCRPage(2,'x')],[GroundTruthPage(1,'abcd'),GroundTruthPage(2,'y')])
 assert result.raw_markdown.character_edits.substitutions==1
 assert result.raw_markdown.character_edits.reference_length==5
 assert result.raw_markdown.cer==pytest.approx(1/5)


def test_weighted_word_aggregation():
 result=score_page_aligned_document([OCRPage(1,'one two three'),OCRPage(2,'x')],[GroundTruthPage(1,'one two three'),GroundTruthPage(2,'y')])
 assert result.raw_markdown.word_edits.substitutions==1
 assert result.raw_markdown.word_edits.reference_length==4
 assert result.raw_markdown.wer==pytest.approx(1/4)


def test_missing_ocr_page_deletion_penalty():
 result=score_page_aligned_document([OCRPage(1,'one')],[GroundTruthPage(1,'one'),GroundTruthPage(2,'two')])
 page=result.pages[1]
 assert not page.ocr_present and page.ground_truth_present
 assert page.raw_markdown.character_edits.deletions==3 and page.raw_markdown.cer==1


def test_extra_ocr_page_insertion_penalty():
 result=score_page_aligned_document([OCRPage(1,'one'),OCRPage(2,'two')],[GroundTruthPage(1,'one')])
 page=result.pages[1]
 assert page.ocr_present and not page.ground_truth_present
 assert page.raw_markdown.cer is None and page.raw_markdown.character_edits.insertions==3
 assert result.raw_markdown.character_edits.insertions==3 and result.raw_markdown.cer==1


def test_missing_middle_page_penalty():
 result=score_page_aligned_document([OCRPage(1,'one'),OCRPage(3,'three')],[GroundTruthPage(1,'one'),GroundTruthPage(2,'two'),GroundTruthPage(3,'three')])
 assert [page.page_number for page in result.pages]==[1,2,3]
 assert result.pages[1].raw_markdown.character_edits.deletions==3


def test_nonconsecutive_page_numbers_align_by_number():
 result=score_page_aligned_document([OCRPage(2,'two'),OCRPage(4,'four')],[GroundTruthPage(2,'two'),GroundTruthPage(4,'four')])
 assert [page.page_number for page in result.pages]==[2,4] and result.raw_markdown.cer==0


def test_swapped_page_contents_are_penalized():
 result=score_page_aligned_document([OCRPage(1,'second'),OCRPage(2,'first')],[GroundTruthPage(1,'first'),GroundTruthPage(2,'second')])
 assert result.raw_markdown.character_edits.substitutions+result.raw_markdown.character_edits.insertions+result.raw_markdown.character_edits.deletions>0


def test_ocr_pages_are_returned_in_fixed_page_number_order():
 result=score_page_aligned_document([OCRPage(3,'three'),OCRPage(1,'one')],[GroundTruthPage(1,'one'),GroundTruthPage(3,'three')])
 assert [page.page_number for page in result.pages]==[1,3]


def test_ground_truth_pages_are_returned_in_fixed_page_number_order():
 result=score_page_aligned_document([OCRPage(2,'two'),OCRPage(1,'one')],[GroundTruthPage(2,'two'),GroundTruthPage(1,'one')])
 assert [page.page_number for page in result.pages]==[1,2]


def test_raw_markdown_mode_uses_page_markdown():
 result=score_page_aligned_document([OCRPage(1,'# Heading\nText')],[GroundTruthPage(1,'Heading\nText')])
 assert result.raw_markdown.cer and result.raw_markdown.cer>0


def test_strict_mode_removes_page_formatting():
 result=score_page_aligned_document([OCRPage(1,'# Heading\nText')],[GroundTruthPage(1,'Heading\nText')])
 assert result.strict_content.cer==0


def test_relaxed_mode_normalizes_whitespace():
 result=score_page_aligned_document([OCRPage(1,'One  \n Two')],[GroundTruthPage(1,'One Two')])
 assert result.relaxed_content.cer==0


def test_document_result_contains_page_details():
 result=score_page_aligned_document([OCRPage(1,'one')],[GroundTruthPage(1,'one')])
 data=multi_page_metric_result_dict(result)
 assert data['pages'][0]['page_number']==1 and 'document_metrics' in data


def test_multi_page_record_uses_page_ground_truth_path(tmp_path):
 path=tmp_path/'pages.json';path.write_text('{"document_id":"x","pages":[{"page_number":1,"text":"one"}]}')
 assert load_page_ground_truth(path)[0].page_number==1


def test_combined_markdown_is_not_scored_as_one_block():
 pages=extract_ocr_pages_from_markdown('## Page 1\nOne\n## Page 2\nTwo')
 result=score_page_aligned_document(pages,[GroundTruthPage(1,'One'),GroundTruthPage(2,'Two')])
 assert len(result.pages)==2 and result.raw_markdown.cer==0


def test_all_canonical_multi_page_shapes_are_page_aligned():
 result=score_page_aligned_document([OCRPage(1,'one'),OCRPage(2,'two'),OCRPage(3,'three')],[GroundTruthPage(1,'one'),GroundTruthPage(2,'two'),GroundTruthPage(3,'three')])
 assert all(page.ocr_present and page.ground_truth_present for page in result.pages)


def _record(document_id, evaluation_type='primary', dpi=200, cer=0.0, wer=0.0, excluded=False):
 return {'record_id':f'{document_id}-{evaluation_type}-{dpi}','document_id':document_id,'evaluation_type':evaluation_type,'dpi':dpi,'excluded':excluded,'metrics':{mode:{'cer':cer,'wer':wer} for mode in ('raw_markdown','strict_content','relaxed_content')}}


def test_category_aggregation_uses_only_primary_records():
 records=[_record('a','primary',200,.1,.1),_record('b','primary',200,.2,.2)]
 assert aggregate_content_metrics(records)['record_count']==2


def test_category_requires_exactly_two_records():
 with pytest.raises(ValueError):
  category_content_aggregates([_record('a')],['category'])


def test_dpi_aggregation_uses_only_canonical_dpi_records():
 records=[_record(str(i),'dpi',150,.1,.1) for i in range(6)]
 assert dpi_content_aggregates(records)['150']['record_count']==6


def test_excluded_dpi_records_are_ignored():
 records=[_record(str(i),'dpi',150,.1,.1) for i in range(6)]+[_record('skip','dpi',150,.9,.9,True)]
 assert dpi_content_aggregates(records)['150']['record_count']==6


def test_zero_nonzero_distribution():
 records=[_record('a',cer=0,wer=0),_record('b',cer=.2,wer=.3)]
 assert metric_distribution(records,'strict_content','cer')['zero_records']==1


def test_percentile_calculation():
 assert percentile([1,2,3,4],75)==3


def test_highest_error_ranking():
 ranked=highest_error_records([_record('a',cer=.1),_record('b',cer=.9)],'relaxed_content','cer')
 assert ranked[0]['document_id']=='b'


def test_numeric_identifier_exact_match():
 r=score_numeric_fields('Invoice INV-2026-001',[{'name':'id','type':'identifier','expected':'INV-2026-001'}])[0]
 assert r['correct']


def test_numeric_identifier_mismatch():
 r=score_numeric_fields('Invoice INV-2026-002',[{'name':'id','type':'identifier','expected':'INV-2026-001'}])[0]
 assert not r['correct'] and r['failure_category']=='IDENTIFIER_MISMATCH'


def test_date_accepted_format():
 r=score_numeric_fields('Date 12/07/2026',[{'name':'date','type':'date','expected':'2026-07-12','accepted_formats':['2026-07-12','12/07/2026']}])[0]
 assert r['correct']


def test_date_mismatch():
 r=score_numeric_fields('Date 13/07/2026',[{'name':'date','type':'date','expected':'2026-07-12'}])[0]
 assert not r['correct'] and r['failure_category']=='DATE_MISMATCH'


def test_currency_normalizes_rp_to_idr():
 r=score_numeric_fields('Total Rp 138.750',[{'name':'total','type':'currency','expected_numeric':'138750','expected_currency':'IDR','currency_required':True}])[0]
 assert r['correct'] and r['observed']=='IDR:138750'


def test_currency_required_but_missing():
 r=score_numeric_fields('Total 138750',[{'name':'total','type':'currency','expected_numeric':'138750','expected_currency':'IDR','currency_required':True}])[0]
 assert not r['correct'] and r['failure_category']=='CURRENCY_MISSING'


def test_grouped_integer_normalization():
 r=score_numeric_fields('Total 1,250,000',[{'name':'total','type':'integer','expected':'1250000'}])[0]
 assert r['correct']


def test_percentage_match():
 assert score_numeric_fields('Tax 11%',[{'name':'tax','type':'percentage','expected':'11'}])[0]['correct']


def test_phone_number_match():
 assert score_numeric_fields('Call +62 812-3456-7890',[{'name':'phone','type':'phone','expected':'6281234567890'}])[0]['correct']


def test_one_ocr_span_is_not_reused():
 r=score_numeric_fields('Qty 5',[{'name':'first','type':'quantity','expected':'5'},{'name':'second','type':'quantity','expected':'5'}])
 assert r[0]['correct'] and not r[1]['correct']


def test_valid_markdown_table_parsing():
 headers,rows=extract_table_cells('| Item | Quantity | Price |\n| --- | --- | --- |\n| Paper | 2 | 15000 |',['Item','Quantity','Price'],1)
 assert headers==['Item','Quantity','Price'] and rows==[['Paper','2','15000']]


def test_broken_table_borders_with_correct_cells():
 result=score_table('Item Quantity Price\nPaper 2 15000',{'headers':['Item','Quantity','Price'],'rows':[['Paper','2','15000']]})
 assert result['overall_cell_accuracy']['accuracy']==1


def test_missing_header_cell():
 result=score_table('Item Price\nPaper 15000',{'headers':['Item','Quantity','Price'],'rows':[['Paper','2','15000']]})
 assert result['header_cell_accuracy']['correct']<3


def test_missing_body_cell():
 result=score_table('Item Quantity Price\nPaper 2',{'headers':['Item','Quantity','Price'],'rows':[['Paper','2','15000']]})
 assert result['body_cell_accuracy']['correct']<3


def test_numeric_cell_mismatch():
 result=score_table('Item Quantity Price\nPaper 2 16000',{'headers':['Item','Quantity','Price'],'rows':[['Paper','2','15000']]})
 assert result['numeric_cell_accuracy']['correct']==1


def test_row_order_mismatch():
 result=score_table('Item Quantity Price\nInk 1 45000\nPaper 2 15000',{'headers':['Item','Quantity','Price'],'rows':[['Paper','2','15000'],['Ink','1','45000']]})
 assert result['row_content_preservation']['correct']==0


def test_overall_table_cell_accuracy():
 result=score_table('Item Quantity Price\nPaper 2 15000',{'headers':['Item','Quantity','Price'],'rows':[['Paper','2','15000']]})
 assert result['overall_cell_accuracy']=={'correct':6,'total':6,'accuracy':1}


def test_numeric_aggregation():
 totals=aggregate_numeric_results([{'type':'identifier','correct':True},{'type':'identifier','correct':False}])
 assert totals['overall']=={'correct':1,'total':2,'accuracy':.5} and totals['identifier']['accuracy']==.5


def test_table_aggregation():
 result=score_table('Item Quantity Price\nPaper 2 15000',{'headers':['Item','Quantity','Price'],'rows':[['Paper','2','15000']]})
 assert aggregate_table_results([result])['overall_cell_accuracy']['accuracy']==1

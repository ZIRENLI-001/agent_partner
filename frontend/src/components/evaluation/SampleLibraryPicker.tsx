import { Alert, Button, List, Modal, Select, Spin, Tag } from "antd";
import { useMemo, useState } from "react";
import { getCalibrationSamples, type CalibrationSample } from "../../api/calibration";

interface SampleLibraryPickerProps {
  onSelect: (sample: CalibrationSample) => void;
  buttonLabel?: string;
}

export function SampleLibraryPicker({ onSelect, buttonLabel = "选择评测样本库" }: SampleLibraryPickerProps) {
  const [open, setOpen] = useState(false);
  const [difficultyFilter, setDifficultyFilter] = useState<string>();
  const [domainFilter, setDomainFilter] = useState<string>();
  const [riskFilter, setRiskFilter] = useState<string>();
  const [samples, setSamples] = useState<CalibrationSample[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function openPicker() {
    setOpen(true);
    if (samples.length || loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await getCalibrationSamples();
      setSamples(response.samples);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  const difficultyOptions = useMemo(
    () => uniqueOptions(samples.map((sample) => sample.difficulty)),
    [samples]
  );
  const domainOptions = useMemo(
    () => uniqueOptions(samples.map((sample) => sample.domain)),
    [samples]
  );
  const riskOptions = useMemo(
    () => uniqueOptions(samples.flatMap((sample) => sample.risk_tags)),
    [samples]
  );
  const filteredSamples = useMemo(
    () =>
      samples.filter((sample) => {
        if (difficultyFilter && sample.difficulty !== difficultyFilter) return false;
        if (domainFilter && sample.domain !== domainFilter) return false;
        if (riskFilter && !sample.risk_tags.includes(riskFilter)) return false;
        return true;
      }),
    [difficultyFilter, domainFilter, riskFilter, samples]
  );

  return (
    <>
      <Button className="mt-action-button" size="small" onClick={openPicker}>
        {buttonLabel}
      </Button>
      <Modal
        className="sample-library-modal"
        title="选择评测样本库"
        open={open}
        footer={null}
        width={860}
        onCancel={() => setOpen(false)}
      >
        <div className="sample-library-filters">
          <Select
            allowClear
            placeholder="难度"
            options={difficultyOptions}
            value={difficultyFilter}
            onChange={setDifficultyFilter}
          />
          <Select
            allowClear
            placeholder="业务域"
            options={domainOptions}
            value={domainFilter}
            onChange={setDomainFilter}
          />
          <Select
            allowClear
            showSearch
            placeholder="风险标签"
            options={riskOptions}
            value={riskFilter}
            onChange={setRiskFilter}
          />
        </div>
        {error ? <Alert className="mb-16" type="error" message={error} /> : null}
        {loading ? <Spin /> : null}
        {!loading ? (
          <List
            className="sample-library-list"
            dataSource={filteredSamples.slice(0, 80)}
            locale={{ emptyText: "暂无匹配样本" }}
            renderItem={(sample) => (
              <List.Item
                actions={[
                  <Button
                    className="mt-action-button"
                    key="select"
                    size="small"
                    onClick={() => {
                      onSelect(sample);
                      setOpen(false);
                    }}
                  >
                    使用该样本
                  </Button>
                ]}
              >
                <List.Item.Meta
                  title={
                    <div className="sample-library-title">
                      <strong>{sample.sample_id}</strong>
                      <Tag>{sample.difficulty}</Tag>
                      <Tag color="gold">{sample.scenario_type}</Tag>
                      <span>{sample.domain}</span>
                    </div>
                  }
                  description={
                    <div className="sample-library-description">
                      <span>{sample.coverage_targets.slice(0, 4).join(" / ")}</span>
                      <span>{sample.risk_tags.slice(0, 5).join("、")}</span>
                      <span>input_variables：{JSON.stringify(sample.input_variables, null, 0)}</span>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        ) : null}
      </Modal>
    </>
  );
}

function uniqueOptions(values: string[]) {
  return Array.from(new Set(values))
    .filter(Boolean)
    .sort()
    .map((value) => ({ label: value, value }));
}
